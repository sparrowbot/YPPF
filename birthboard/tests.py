from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
from django.utils import timezone
from django.core.management import call_command
from django.urls import reverse

import os
from datetime import datetime, timedelta
from unittest.mock import patch

from birthboard.models import BirthboardRecord, BirthboardParticipant, BirthboardRejectedIssue, ChangeRecord
from birthboard.utils import calculate_per_cost
from birthboard.views import _deduct_and_mark_paid, _reject_record_by_admin, _refund_paid_participants_and_terminate
from birthboard.reminder import (
    _first_reminder_times,
    _second_reminder_times,
    _send_approval_reminder,
    schedule_first_approval_reminders,
    cancel_approval_reminders,
)
from birthboard import jobs as bb_jobs
from birthboard import views as bb_views
from generic.models import YQPointRecord


User = get_user_model()


class BirthboardUtilsTests(TestCase):
	def test_calculate_per_cost_basic(self):
		self.assertEqual(calculate_per_cost(0, 2), 17)
		self.assertEqual(calculate_per_cost(1, 3), 20)

	def test_calculate_per_cost_min_floor(self):
		# 35 / 10 = 3, still above minimum 2
		self.assertEqual(calculate_per_cost(0, 10), 3)

	def test_calculate_per_cost_invalid_mode(self):
		# invalid mode falls back to mode 0
		self.assertEqual(calculate_per_cost(999, 2), 17)


class BirthboardViewHelperTests(TestCase):
	def setUp(self):
		self.sender = User.objects.create_user(username="sender", name="Sender", password="test")
		self.receiver = User.objects.create_user(username="receiver", name="Receiver", password="test")
		self.sender.YQpoint = 50
		self.sender.save(update_fields=["YQpoint"])

	def _create_record_with_participant(self, participant_status=BirthboardParticipant.Status.WAIT):
		image = SimpleUploadedFile("test.jpg", b"fake-image", content_type="image/jpeg")
		record = BirthboardRecord.objects.create(
			receiver_username=self.receiver.username,
			receiver_name=self.receiver.username,
			date="2026-04-20",
			mode=0,
			per_cost=10,
			image=image,
			is_anonymous=False,
			status=BirthboardRecord.Status.WAITING_CONFIRM,
		)
		participant = BirthboardParticipant.objects.create(
			record=record,
			user=self.sender,
			role=BirthboardParticipant.Role.SENDER,
			is_initiator=True,
			cost=10,
			status=participant_status,
		)
		return record, participant

	def test_deduct_and_mark_paid_success(self):
		_, participant = self._create_record_with_participant()

		result = _deduct_and_mark_paid(self.sender, participant, 10)

		self.assertTrue(result)
		participant.refresh_from_db()
		self.sender.refresh_from_db()
		self.assertEqual(participant.status, BirthboardParticipant.Status.PAID)
		self.assertIsNotNone(participant.action_time)
		self.assertEqual(self.sender.YQpoint, 40)
		self.assertEqual(YQPointRecord.objects.filter(user=self.sender, delta=-10, source="birthboard").count(), 1)

	def test_deduct_and_mark_paid_insufficient(self):
		_, participant = self._create_record_with_participant()

		result = _deduct_and_mark_paid(self.sender, participant, 1000)

		self.assertFalse(result)
		participant.refresh_from_db()
		self.sender.refresh_from_db()
		self.assertEqual(participant.status, BirthboardParticipant.Status.WAIT)
		self.assertEqual(self.sender.YQpoint, 50)
		self.assertEqual(YQPointRecord.objects.filter(user=self.sender, source="birthboard").count(), 0)

	def test_reject_record_by_admin_upserts_issue(self):
		record, _ = self._create_record_with_participant()

		_reject_record_by_admin(record, ["低俗恶搞"], "first")
		_reject_record_by_admin(record, ["敏感引战"], "second")

		record.refresh_from_db()
		self.assertEqual(record.status, BirthboardRecord.Status.TERMINATED_BY_ADMIN)
		self.assertEqual(BirthboardRejectedIssue.objects.filter(record=record).count(), 1)
		issue = BirthboardRejectedIssue.objects.get(record=record)
		self.assertEqual(issue.reasons, "敏感引战")
		self.assertEqual(issue.detail, "second")

	def test_refund_paid_participants_and_terminate_logs_change(self):
		record, participant = self._create_record_with_participant(participant_status=BirthboardParticipant.Status.PAID)
		self.sender.YQpoint = 40
		self.sender.save(update_fields=["YQpoint"])

		_refund_paid_participants_and_terminate(
			record,
			actor=self.sender,
			action=ChangeRecord.Action.ABORT,
			detail={"scope": "initiator_abort"},
		)

		record.refresh_from_db()
		participant.refresh_from_db()
		self.sender.refresh_from_db()
		self.assertEqual(record.status, BirthboardRecord.Status.TERMINATED)
		self.assertEqual(participant.status, BirthboardParticipant.Status.REFUNDED)
		self.assertEqual(self.sender.YQpoint, 50)
		self.assertEqual(ChangeRecord.objects.filter(record=record, action=ChangeRecord.Action.ABORT).count(), 1)
		change = ChangeRecord.objects.get(record=record, action=ChangeRecord.Action.ABORT)
		self.assertEqual(change.actor, self.sender)
		self.assertEqual(change.before_status, BirthboardRecord.Status.WAITING_CONFIRM)
		self.assertEqual(change.after_status, BirthboardRecord.Status.TERMINATED)
		self.assertEqual(change.detail.get("scope"), "initiator_abort")


class BirthboardNightlyJobsTests(TestCase):
	def setUp(self):
		self.img1 = SimpleUploadedFile("test1.jpg", b"fake-image-1", content_type="image/jpeg")
		self.img2 = SimpleUploadedFile("test2.jpg", b"fake-image-2", content_type="image/jpeg")

	@patch("playwright.sync_api.sync_playwright")
	@patch("birthboard.web_controller._run_update_cycle")
	@patch("birthboard.web_controller.open_and_login")
	def test_nightly_update_2345_transitions_and_calls_update_cycle(
		self, mock_open, mock_update, mock_playwright,
	):
		mock_open.return_value = (object(), object())
		mock_update.return_value = (object(), object(), {})

		now = timezone.now()
		today = timezone.localtime(now).date() if timezone.is_aware(now) else now.date()
		target_date = today + timedelta(days=1)

		rec_start = BirthboardRecord.objects.create(
			receiver_username="r1",
			receiver_name="r1",
			date=target_date,
			mode=0,
			per_cost=1,
			image=self.img1,
			status=BirthboardRecord.Status.READY,
		)
		rec_finish = BirthboardRecord.objects.create(
			receiver_username="r2",
			receiver_name="r2",
			date=target_date - timedelta(days=3),
			mode=1,
			per_cost=1,
			image=self.img2,
			status=BirthboardRecord.Status.ONGOING,
		)

		bb_jobs.birthboard_nightly_update_2345()

		rec_start.refresh_from_db()
		rec_finish.refresh_from_db()
		self.assertEqual(rec_start.status, BirthboardRecord.Status.ONGOING)
		self.assertEqual(rec_finish.status, BirthboardRecord.Status.FINISHED)

		self.assertEqual(mock_update.call_count, 1)
		kwargs = mock_update.call_args.kwargs
		self.assertIn(os.path.abspath(rec_start.image.path), kwargs["up_image_name"])
		self.assertIn(os.path.abspath(rec_finish.image.path), kwargs["del_image_name"])


class BirthboardLockCoordinationTests(TestCase):
	def setUp(self):
		self.img = SimpleUploadedFile("test3.jpg", b"fake-image-3", content_type="image/jpeg")

	def test_handle_revoke_respects_lock(self):
		rec = BirthboardRecord.objects.create(
			receiver_username="x",
			receiver_name="x",
			date=timezone.now().date(),
			mode=0,
			per_cost=1,
			image=self.img,
			status=BirthboardRecord.Status.READY,
		)

		cache.set(bb_views._BB_UPDATE_LOCK_KEY, True, timeout=300)
		bb_views._handle_revoke(str(rec.id), actor=None)
		rec.refresh_from_db()
		self.assertEqual(rec.status, BirthboardRecord.Status.READY)

		cache.delete(bb_views._BB_UPDATE_LOCK_KEY)
		bb_views._handle_revoke(str(rec.id), actor=None)
		rec.refresh_from_db()
		self.assertEqual(rec.status, BirthboardRecord.Status.CANCELED)


class LockUiIntegrationTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username="tester", name="Tester", password="test")
		self.approver = User.objects.create_user(username="approver", name="Approver", password="test")
		from birthboard.models import BirthboardApprover, BirthboardContract
		BirthboardApprover.objects.create(user=self.approver, is_active=True)
		BirthboardContract.objects.create(user=self.user, signed=True)
		BirthboardContract.objects.create(user=self.approver, signed=True)

	def test_confirm_page_shows_disabled_revoke_when_locked(self):
		self.client.login(username="tester", password="test")
		img = SimpleUploadedFile("img.jpg", b"img", content_type="image/jpeg")
		rec = BirthboardRecord.objects.create(
			receiver_username=self.user.username,
			receiver_name=self.user.username,
			date=timezone.now().date(),
			mode=0,
			per_cost=1,
			image=img,
			status=BirthboardRecord.Status.READY,
		)
		# set lock
		from django.core.cache import cache
		cache.set("birthboard:update_in_progress", True, timeout=300)

		resp = self.client.get(
			reverse('birthboard_confirm') + '?tab=received',
			HTTP_REFERER='/birthboard/',
		)
		content = resp.content.decode('utf-8')
		self.assertIn('23点45-24点系统同步中，无法操作', content)
		self.assertIn('disabled', content)
		# clean
		cache.delete("birthboard:update_in_progress")

	def test_approve_page_shows_only_one_pending_request(self):
		self.client.login(username="approver", password="test")
		img1 = SimpleUploadedFile("img2.jpg", b"img2", content_type="image/jpeg")
		img2 = SimpleUploadedFile("img3.jpg", b"img3", content_type="image/jpeg")
		rec1 = BirthboardRecord.objects.create(
			receiver_username="someone1",
			receiver_name="someone1",
			date=timezone.now().date(),
			mode=0,
			per_cost=1,
			image=img1,
			status=BirthboardRecord.Status.WAITING_APPROVE,
		)
		BirthboardRecord.objects.filter(pk=rec1.pk).update(created_at=timezone.now() - timedelta(minutes=5))
		rec2 = BirthboardRecord.objects.create(
			receiver_username="someone2",
			receiver_name="someone2",
			date=timezone.now().date(),
			mode=0,
			per_cost=1,
			image=img2,
			status=BirthboardRecord.Status.WAITING_APPROVE,
		)
		resp = self.client.get(reverse('birthboard_approve'))
		content = resp.content.decode('utf-8')
		self.assertIn('someone2', content)
		self.assertIn('初审通过', content)
		# 待审核卡片按创建时间倒序，只挑最新一条作为当前审核对象
		current = resp.context['current_activity']
		self.assertIsNotNone(current)
		self.assertEqual(current['record'].pk, rec2.pk)

	def test_approve_page_shows_empty_state_when_no_pending(self):
		self.client.login(username="approver", password="test")
		resp = self.client.get(reverse('birthboard_approve'))
		content = resp.content.decode('utf-8')
		self.assertIn('无需燕牌 暂德清闲', content)


class BirthboardNightlySimulationCommandTests(TestCase):
	@patch("birthboard.jobs.birthboard_nightly_update_2345")
	def test_simulation_command_runs_job(self, mock_2345):
		call_command("simulate_birthboard_nightly_update")
		mock_2345.assert_called_once()


class BirthboardApprovalReminderTests(TestCase):
	"""审核提醒的排期时间与调度测试。"""

	def _make_record(self, date="2026-08-19"):
		image = SimpleUploadedFile("test.jpg", b"fake-image", content_type="image/jpeg")
		return BirthboardRecord.objects.create(
			receiver_username="receiver",
			receiver_name="receiver",
			date=datetime.strptime(date, "%Y-%m-%d").date(),
			mode=0,
			per_cost=10,
			image=image,
			status=BirthboardRecord.Status.WAITING_APPROVE,
		)

	# ---- 时间计算 ----

	def test_first_reminder_times_full(self):
		record = self._make_record("2026-08-19")
		now = datetime(2026, 8, 10, 0, 0)
		times = _first_reminder_times(record, now)
		# D-5/D-4 每天 9:00、14:00 共 4 个；D-3~D-1 每天 9:00~23:00 共 45 个
		self.assertEqual(len(times), 49)
		self.assertIn(datetime(2026, 8, 14, 9, 0), times)
		self.assertIn(datetime(2026, 8, 15, 14, 0), times)
		self.assertIn(datetime(2026, 8, 18, 23, 0), times)

	def test_first_reminder_times_filters_past(self):
		record = self._make_record("2026-08-19")
		now = datetime(2026, 8, 18, 12, 0)
		times = _first_reminder_times(record, now)
		self.assertEqual(len(times), 11)  # 只剩 D-1 13:00~23:00
		self.assertTrue(all(t > now for t in times))

	def test_second_reminder_times_full(self):
		record = self._make_record("2026-08-19")
		now = datetime(2026, 8, 15, 0, 0)  # 早于 D-2
		times = _second_reminder_times(record, now)
		# D-2 9:00、14:00 + D-1 9:00~23:00 共 15 个 = 17 个
		self.assertEqual(len(times), 17)
		self.assertIn(datetime(2026, 8, 17, 9, 0), times)
		self.assertIn(datetime(2026, 8, 17, 14, 0), times)
		self.assertIn(datetime(2026, 8, 18, 23, 0), times)

	def test_second_reminder_times_skips_past_when_late(self):
		record = self._make_record("2026-08-19")
		now = datetime(2026, 8, 17, 10, 0)  # D-2 当天进入二审
		times = _second_reminder_times(record, now)
		# 跳过 D-2 9:00，保留 D-2 14:00 + D-1 15 个 = 16 个
		self.assertNotIn(datetime(2026, 8, 17, 9, 0), times)
		self.assertIn(datetime(2026, 8, 17, 14, 0), times)
		self.assertEqual(len(times), 16)

	# ---- 发送幂等 ----

	@patch("birthboard.notify.notify_approval_reminder")
	def test_send_approval_reminder_skips_when_not_pending(self, mock_notify):
		record = self._make_record("2026-08-19")
		record.status = BirthboardRecord.Status.READY
		record.save(update_fields=["status"])
		_send_approval_reminder(record.id, "first")
		mock_notify.assert_not_called()

	@patch("birthboard.notify.notify_approval_reminder")
	def test_send_approval_reminder_skips_when_first_already_done(self, mock_notify):
		record = self._make_record("2026-08-19")
		record.first_approved = True
		record.save(update_fields=["first_approved"])
		_send_approval_reminder(record.id, "first")
		mock_notify.assert_not_called()

	@patch("birthboard.notify.notify_approval_reminder")
	def test_send_approval_reminder_calls_notify_when_pending(self, mock_notify):
		record = self._make_record("2026-08-19")
		_send_approval_reminder(record.id, "first")
		mock_notify.assert_called_once()
		args, _ = mock_notify.call_args
		self.assertEqual(args[0].id, record.id)
		self.assertEqual(args[1], "first")

	# ---- 调度/撤回 ----

	@patch("birthboard.reminder.ScheduleAdder")
	@patch("birthboard.reminder._first_reminder_times", return_value=[datetime(2026, 8, 14, 9, 0)])
	def test_schedule_first_approval_reminders(self, mock_times, mock_adder):
		record = self._make_record("2026-08-19")
		schedule_first_approval_reminders(record)
		mock_adder.assert_called_once()
		_, kwargs = mock_adder.call_args
		self.assertEqual(kwargs["run_time"], datetime(2026, 8, 14, 9, 0))
		self.assertEqual(kwargs["id"], f"birthboard_approve_remind_{record.id}_first_202608140900")

	@patch("birthboard.reminder.remove_job")
	def test_cancel_approval_reminders(self, mock_remove):
		record = self._make_record("2026-08-19")
		job = type("Job", (), {"id": f"birthboard_approve_remind_{record.id}_first_202608140900"})()
		with patch("birthboard.reminder.scheduler.get_jobs", return_value=[job]):
			cancel_approval_reminders(record, stage="first")
		mock_remove.assert_called_once_with(job.id)
