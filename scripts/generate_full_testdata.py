#!/usr/bin/env python3
"""Generate a full set of random test records for YPPF.

This script creates representative data for the major data models in the
project, including generic users, organizations, activities, courses,
appointments, dormitory records, library records, notifications, logs, and more.

Run from repository root:
    python scripts/generate_full_testdata.py
"""

import os
import sys
import random
from datetime import datetime, timedelta, time

import django

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(PROJECT_ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'boot.settings')
django.setup()

from django.contrib.auth.models import Permission
from django.db import transaction
from faker import Faker

from generic.models import User, PermissionBlacklist, CreditRecord, YQPointRecord
from semester.models import SemesterType, Semester
from app.models import (
    NaturalPerson,
    OrganizationType,
    OrganizationTag,
    Organization,
    CommentBase,
    Comment,
    CommentPhoto,
    Help,
    Wishes,
    ModifyRecord,
    ModifyOrganization,
    ModifyPosition,
    Activity,
    ActivityPhoto,
    Participation,
    Notification,
    Course,
    CourseTime,
    CourseParticipant,
    CourseRecord,
    AcademicTag,
    AcademicEntry,
    AcademicTagEntry,
    AcademicTextEntry,
    Chat,
    AcademicQA,
    AcademicQAAwards,
    Prize,
    Pool,
    PoolItem,
    PoolRecord,
    ActivitySummary,
    HomepageImage,
)
from Appointment.models import (
    College_Announcement,
    Participant as AppointmentParticipant,
    Room,
    Appoint,
    CardCheckInfo,
    LongTermAppoint,
)
from dormitory.models import Agreement, Dormitory, DormitoryAssignment
from yp_library.models import Reader, Book, LendRecord
from record.models import PageLog, ModuleLog

fake = Faker('zh_CN')
random.seed(2026)
CREATED_CREDENTIALS = []

USER_COUNT = 1000
ORG_COUNT = 6
ORG_TYPE_COUNT = 4
ORG_TAG_COUNT = 6
ROOM_COUNT = 4
ACTIVITY_COUNT = 4
COURSE_COUNT = 3
POOL_COUNT = 2
BOOK_COUNT = 6
LEND_COUNT = 6
LOG_COUNT = 6


def unique_username() -> str:
    """Build a stable unique username for the current database."""
    for _ in range(1000):
        username = str(fake.random_int(min=10000000, max=99999999))
        if not User.objects.filter(username=username).exists():
            return username
    raise RuntimeError('Unable to generate a unique username')


def get_choice_values(model, field_name):
    field = model._meta.get_field(field_name)
    return [value for value, label in field.choices if value != '']


def create_user(name: str | None = None,
                email: str | None = None,
                utype: str | None = None) -> User:
    username = unique_username()
    name = name or fake.name()
    email = email or fake.email()
    if utype is None:
        utype = random.choice([User.Type.STUDENT, User.Type.TEACHER, User.Type.PERSON])
    password = 'Passw0rd!2026'
    user = User.objects.create_user(
        username=username,
        name=name,
        email=email,
        password=password,
        usertype=utype,
    )
    CREATED_CREDENTIALS.append((username, password, str(utype)))
    return user


def create_semesters():
    types = []
    for name in ['春季', '秋季', '暑期']:
        types.append(SemesterType.objects.get_or_create(name=name)[0])

    current_year = datetime.now().year
    Semester.objects.get_or_create(
        year=current_year,
        type=types[0],
        defaults={'start_date': datetime(current_year, 2, 1).date(),
                  'end_date': datetime(current_year, 7, 1).date()},
    )
    Semester.objects.get_or_create(
        year=current_year,
        type=types[1],
        defaults={'start_date': datetime(current_year, 9, 1).date(),
                  'end_date': datetime(current_year + 1, 1, 15).date()},
    )
    return types


def create_generic_records(users):
    if Permission.objects.exists():
        PermissionBlacklist.objects.get_or_create(
            user=users[0],
            permission=Permission.objects.first(),
        )
    CreditRecord.objects.create(
        user=users[0],
        old_credit=3,
        new_credit=2,
        delta=-1,
        overflow=False,
        source='test-seed',
    )
    YQPointRecord.objects.create(
        user=users[0],
        delta=50,
        source='seed',
        source_type=YQPointRecord.SourceType.SYSTEM,
    )


def create_persons_and_orgs():
    persons = []
    teachers = []
    org_types = []
    org_tags = []
    organizations = []

    for i in range(ORG_TYPE_COUNT):
        org_types.append(
            OrganizationType.objects.get_or_create(
                otype_id=i + 1,
                defaults={
                    'otype_name': fake.company()[:25],
                    'otype_superior_id': 0,
                    'job_name_list': [fake.job()[:10] for _ in range(2)],
                },
            )[0]
        )

    for i in range(ORG_TAG_COUNT):
        org_tags.append(
            OrganizationTag.objects.get_or_create(
                name=fake.word()[:10],
                defaults={'color': random.choice([c[0] for c in OrganizationTag.ColorChoice.choices])},
            )[0]
        )

    for _ in range(USER_COUNT):
        identity = random.choice([NaturalPerson.Identity.STUDENT, NaturalPerson.Identity.TEACHER])
        user = create_user(utype=User.Type.STUDENT if identity == NaturalPerson.Identity.STUDENT else User.Type.TEACHER)
        person = NaturalPerson.objects.create(
            user,
            name=user.name,
            nickname=fake.first_name(),
            gender=random.choice([0, 1]),
            birthday=fake.date_of_birth(minimum_age=18, maximum_age=30),
            email=user.email,
            telephone=fake.phone_number(),
            biography=fake.text(max_nb_chars=120),
            inform_share=random.choice([True, False]),
            last_time_login=fake.date_time_this_year(),
            identity=identity,
            stu_class=str(random.randint(1, 9)),
            stu_major=fake.word()[:25],
            stu_grade=str(random.randint(1, 4)),
            stu_dorm=f"{random.randint(1, 9)}{random.randint(0, 99):02d}",
            status=random.choice([
                NaturalPerson.GraduateStatus.UNDERGRADUATED,
                NaturalPerson.GraduateStatus.POSTPONED,
            ]),
            show_nickname=random.choice([True, False]),
            show_birthday=random.choice([True, False]),
            show_gender=random.choice([True, False]),
            show_email=random.choice([True, False]),
            show_tel=random.choice([True, False]),
            show_major=random.choice([True, False]),
            show_dorm=random.choice([True, False]),
            permissions={
                'select_course': random.choice([True, False]),
                'gain_credit': random.choice([True, False]),
            },
            active_score=random.random() * 10,
        )
        persons.append(person)
        if identity == NaturalPerson.Identity.TEACHER:
            teachers.append(person)

    if not teachers:
        teacher_user = create_user(utype=User.Type.TEACHER)
        teacher = NaturalPerson.objects.create(
            teacher_user,
            name=teacher_user.name,
            nickname=fake.first_name(),
            gender=random.choice([0, 1]),
            identity=NaturalPerson.Identity.TEACHER,
            status=NaturalPerson.GraduateStatus.UNDERGRADUATED,
        )
        teachers.append(teacher)
        persons.append(teacher)

    for _ in range(ORG_COUNT):
        org_user = create_user(utype=User.Type.ORG)
        org = Organization.objects.create(
            organization_id=org_user,
            oname=fake.unique.company()[:32],
            otype=random.choice(org_types),
            status=random.choice([True, True, False]),
            introduction=fake.text(max_nb_chars=120),
            avatar='',
            wallpaper='',
            inform_share=random.choice([True, False]),
            visit_times=random.randint(0, 300),
        )
        org.tags.add(*random.sample(org_tags, min(3, len(org_tags))))
        organizations.append(org)

    for person in persons:
        if organizations and random.random() < 0.3:
            person.unsubscribe_list.add(*random.sample(organizations, min(2, len(organizations))))

    return persons, teachers, organizations, org_types, org_tags


def create_help_wishes_modify_records(users):
    Help.objects.create(title='测试帮助', content=fake.text(max_nb_chars=120))
    Wishes.objects.create(text=fake.sentence(), background=Wishes.rand_color())
    ModifyRecord.objects.create(
        user=users[0],
        usertype=users[0].utype,
        name=users[0].name,
        info='自动生成的修改记录',
    )


def create_comment_and_notification(users):
    base = CommentBase.objects.create()
    comment = Comment.objects.create(
        commentator=users[0],
        commentbase=base,
        text=fake.sentence(nb_words=20),
    )
    CommentPhoto.objects.create(comment=comment, image='comment/seed.jpg')
    Notification.objects.create(
        receiver=users[1 % len(users)],
        sender=users[0],
        status=Notification.Status.UNDONE,
        title=Notification.Title.ACTIVITY_INFORM,
        content=fake.text(max_nb_chars=100),
        URL='https://example.com',
        bulk_identifier='seed-batch',
        anonymous_flag=False,
        relate_instance=base,
    )
    return base


def create_activity_data(persons, organizations, teachers):
    activities = []
    status_values = [s[0] for s in Activity.Status.choices]
    semester_values = get_choice_values(Activity, 'semester')
    for _ in range(ACTIVITY_COUNT):
        org = random.choice(organizations)
        teacher = random.choice(teachers)
        start = datetime.now() + timedelta(days=random.randint(1, 30), hours=random.randint(7, 20))
        end = start + timedelta(hours=random.randint(1, 5))
        activity = Activity.objects.create(
            title=fake.sentence(nb_words=6)[:50],
            organization_id=org,
            year=datetime.now().year,
            semester=random.choice(semester_values),
            publish_day=random.choice([0, 1, 2, 3]),
            publish_time=datetime.now(),
            need_apply=random.choice([True, False]),
            endbefore=random.choice([0, 1, 2, 3]),
            apply_end=start - timedelta(days=1),
            start=start,
            end=end,
            location=fake.city(),
            introduction=fake.text(max_nb_chars=120),
            bidding=random.choice([True, False]),
            need_checkin=random.choice([True, False]),
            visit_times=random.randint(0, 200),
            examine_teacher=teacher,
            recorded=random.choice([True, False]),
            valid=random.choice([True, False]),
            inner=random.choice([True, False]),
            capacity=random.randint(10, 80),
            current_participants=0,
            URL=fake.url(),
            status=random.choice(status_values),
            category=random.choice([0, 1]),
        )
        ActivityPhoto.objects.create(
            type=random.choice([0, 1]),
            image='activity/photo/seed.jpg',
            activity=activity,
        )
        activities.append(activity)

    for activity in activities:
        attending = random.sample(persons, min(4, len(persons)))
        for person in attending:
            Participation.objects.create(
                activity=activity,
                person=person,
                status=random.choice([Participation.AttendStatus.APPLYSUCCESS,
                                      Participation.AttendStatus.ATTENDED,
                                      Participation.AttendStatus.UNATTENDED]),
            )
    ActivitySummary.objects.create(
        activity=random.choice(activities),
        status=ActivitySummary.Status.WAITING,
        image='ActivitySummary/photo/seed.jpg',
    )
    HomepageImage.objects.create(
        redirect_url='/sample',
        image='homepage_image/seed.jpg',
        description='首页测试图片',
        sort_id=0,
        activated=True,
    )
    return activities


def create_course_data(persons, organizations):
    courses = []
    course_statuses = [s[0] for s in Course.Status.choices]
    course_types = [t[0] for t in Course.CourseType.choices]
    semester_values = get_choice_values(Course, 'semester')
    for _ in range(COURSE_COUNT):
        course = Course.objects.create(
            name=fake.sentence(nb_words=3)[:60],
            organization=random.choice(organizations),
            year=datetime.now().year,
            semester=random.choice(semester_values),
            times=random.randint(8, 16),
            hours_per_class=random.choice([1.5, 2.0, 2.5]),
            classroom=fake.word()[:60],
            teacher=fake.name()[:48],
            introduction=fake.text(max_nb_chars=120),
            teaching_plan=fake.text(max_nb_chars=120),
            record_cal_method=fake.text(max_nb_chars=100),
            status=random.choice(course_statuses),
            type=random.choice(course_types),
            capacity=random.randint(20, 80),
            current_participants=0,
            publish_day=random.choice([0, 1, 2, 3]),
            need_apply=random.choice([True, False]),
            photo='course/photo/seed.jpg',
            QRcode='course/QRcode/seed.png',
        )
        CourseTime.objects.create(
            course=course,
            start=datetime.now() + timedelta(days=random.randint(1, 10)),
            end=datetime.now() + timedelta(days=random.randint(11, 20)),
            cur_week=0,
            end_week=course.times,
        )
        courses.append(course)

    for course in courses:
        students = random.sample(persons, min(4, len(persons)))
        for person in students:
            CourseParticipant.objects.create(
                course=course,
                person=person,
                status=random.choice([CourseParticipant.Status.SELECT,
                                      CourseParticipant.Status.SUCCESS,
                                      CourseParticipant.Status.FAILED]),
            )
            attend_times = random.randint(0, course.times)
            hours_per_class = course.hours_per_class
            bonus_hours = random.choice([0.0, 1.0, 2.0])
            CourseRecord.objects.create(
                person=person,
                course=course,
                extra_name='',
                year=course.year,
                semester=course.semester,
                total_hours=bonus_hours + attend_times * hours_per_class,
                attend_times=attend_times,
                hours_per_class=hours_per_class,
                bonus_hours=bonus_hours,
                invalid=False,
            )
    return courses


def create_academic_data(persons, users):
    tags = []
    for _ in range(3):
        tags.append(
            AcademicTag.objects.create(
                atype=random.choice([0, 1, 2, 3]),
                tag_content=fake.word()[:63],
            )
        )
    for person in persons[:3]:
        AcademicTagEntry.objects.create(
            person=person,
            status=AcademicEntry.EntryStatus.PUBLIC,
            tag=random.choice(tags),
        )
        AcademicTextEntry.objects.create(
            person=person,
            status=AcademicEntry.EntryStatus.PUBLIC,
            atype=random.choice([0, 1, 2, 3, 4]),
            content=fake.text(max_nb_chars=120),
        )
    for u in users[:2]:
        chat = Chat.objects.create(
            questioner=u,
            respondent=users[(users.index(u) + 1) % len(users)],
            title=fake.sentence(nb_words=5)[:50],
            questioner_anonymous=random.choice([True, False]),
            respondent_anonymous=random.choice([True, False]),
            status=Chat.Status.PROGRESSING,
        )
        AcademicQA.objects.create(
            chat=chat,
            keywords=[fake.word() for _ in range(3)],
            directed=random.choice([True, False]),
            rating=random.randint(0, 5),
        )
    for user in users[:2]:
        AcademicQAAwards.objects.get_or_create(user=user)


def create_prize_pool_data(users, activities):
    prizes = []
    pools = []
    for _ in range(3):
        prizes.append(
            Prize.objects.create(
                name=fake.word()[:50],
                more_info=fake.sentence(nb_words=8),
                stock=random.randint(1, 20),
                reference_price=random.randint(10, 200),
                image='prize/seed.png',
                provider=random.choice(users),
            )
        )
    for _ in range(POOL_COUNT):
        pools.append(
            Pool.objects.create(
                title=fake.sentence(nb_words=3)[:50],
                type=random.choice([choice[0] for choice in Pool.Type.choices]),
                entry_time=random.randint(1, 5),
                ticket_price=random.randint(0, 50),
                empty_YQPoint_compensation_lowerbound=random.randint(0, 10),
                empty_YQPoint_compensation_upperbound=random.randint(10, 50),
                start=datetime.now() - timedelta(days=1),
                end=datetime.now() + timedelta(days=30),
                redeem_start=datetime.now() + timedelta(days=15),
                redeem_end=datetime.now() + timedelta(days=40),
                activity=random.choice(activities) if activities else None,
            )
        )
    for pool in pools:
        for prize in random.sample(prizes, min(2, len(prizes))):
            PoolItem.objects.create(
                pool=pool,
                prize=prize,
                origin_num=random.randint(1, 20),
                consumed_num=random.randint(0, 5),
                exchange_limit=random.randint(0, 5),
                exchange_price=random.randint(0, 100),
                exchange_attributes={'rarity': fake.word()},
                is_big_prize=random.choice([True, False]),
                is_empty_prize=random.choice([False, True]),
            )
    statuses = [choice[0] for choice in PoolRecord.Status.choices]
    for i in range(min(len(users), len(pools))):
        PoolRecord.objects.create(
            user=users[i],
            pool=pools[i],
            prize=random.choice(prizes),
            attributes={'note': fake.word()},
            status=random.choice(statuses),
            redeem_time=datetime.now() + timedelta(days=random.randint(1, 10)),
        )


def create_appointment_data(users):
    rooms = []
    for i in range(ROOM_COUNT):
        rooms.append(
            Room.objects.create(
                Rid=f'R{100 + i}',
                Rtitle=fake.word()[:16],
                Rmin=random.randint(1, 3),
                Rmax=random.randint(5, 20),
                Rstart=time(8, 0),
                Rfinish=time(22, 0),
                Rpresent=random.randint(0, 5),
                Rstatus=random.choice([0, 1, 2]),
                RIsAllNight=random.choice([True, False]),
                RneedAgree=random.choice([True, False]),
            )
        )
    appointment_users = users[:6]
    participants = []
    for user in appointment_users:
        participants.append(AppointmentParticipant.objects.create(Sid=user))

    appoints = []
    for i in range(4):
        major_student = random.choice(participants)
        selected_students = random.sample(participants, min(3, len(participants)))
        start = datetime.now() + timedelta(days=random.randint(1, 10), hours=random.randint(8, 18))
        appoint = Appoint.objects.create(
            Astart=start,
            Afinish=start + timedelta(hours=2),
            Ausage=fake.word()[:32],
            Aannouncement=fake.sentence(nb_words=6)[:128],
            Anon_yp_num=random.randint(0, 2),
            Ayp_num=random.randint(0, 4),
            Room=random.choice(rooms),
            major_student=major_student,
            Astatus=random.choice([s[0] for s in Appoint.Status.choices]),
            Aneed_num=random.randint(1, 5),
            Areason=random.choice([r[0] for r in Appoint.Reason.choices]),
            Atype=random.choice([t[0] for t in Appoint.Type.choices]),
            Acamera_check_num=random.randint(0, 3),
            Acamera_ok_num=random.randint(0, 3),
        )
        appoint.students.add(*selected_students)
        appoints.append(appoint)

    for participant in participants[:3]:
        CardCheckInfo.objects.create(
            Cardroom=random.choice(rooms),
            Cardstudent=participant,
            CardStatus=random.choice([0, 1]),
            Message=fake.sentence(nb_words=8),
        )
    for appoint in appoints[:2]:
        LongTermAppoint.objects.create(
            appoint=appoint,
            applicant=random.choice(participants),
            times=random.randint(2, 4),
            interval=random.randint(1, 2),
            review_comment=fake.text(max_nb_chars=80),
            status=random.choice([s[0] for s in LongTermAppoint.Status.choices]),
        )
    College_Announcement.objects.create(show=1, announcement=fake.text(max_nb_chars=80))


def create_dormitory_data(users):
    dorms = []
    for letter, gender in [('A', 'M'), ('B', 'F')]:
        dorms.append(Dormitory.objects.create(capacity=4, gender=gender))
    for bed_id, user in enumerate(users[:4], start=1):
        DormitoryAssignment.objects.create(
            dormitory=random.choice(dorms),
            user=user,
            bed_id=bed_id,
            active=random.choice([True, False]),
        )
        Agreement.objects.create(user=user)


def create_library_data(users):
    readers = []
    for user in users[:4]:
        readers.append(Reader.objects.create(student_id=user.username))
    books = []
    for i in range(BOOK_COUNT):
        books.append(
            Book.objects.create(
                id=1000 + i,
                identity_code=fake.bothify(text='??-####'),
                title=fake.sentence(nb_words=4)[:80],
                author=fake.name()[:50],
                publisher=fake.company()[:50],
                returned=random.choice([True, False]),
            )
        )
    for i in range(LEND_COUNT):
        reader = random.choice(readers)
        book = random.choice(books + [None])
        lend_time = datetime.now() - timedelta(days=random.randint(1, 30))
        return_time = lend_time + timedelta(days=random.randint(1, 30)) if random.choice([True, False]) else None
        LendRecord.objects.create(
            id=2000 + i,
            reader_id=reader,
            book_id=book,
            lend_time=lend_time,
            due_time=lend_time + timedelta(days=14),
            return_time=return_time,
            returned=return_time is not None,
            status=random.choice([s[0] for s in LendRecord.Status.choices]),
        )


def create_record_logs(users):
    for i in range(LOG_COUNT):
        PageLog.objects.create(
            user=random.choice(users),
            type=random.choice([PageLog.CountType.PV, PageLog.CountType.PD]),
            page=fake.url(),
            time=datetime.now() - timedelta(days=random.randint(0, 5)),
            platform=random.choice(['Web', 'iOS', 'Android']),
            explore_name='Chrome',
            explore_version='114.0',
        )
        ModuleLog.objects.create(
            user=random.choice(users),
            type=random.choice([ModuleLog.CountType.MV, ModuleLog.CountType.MC]),
            page=fake.url(),
            module_name=fake.word()[:32],
            time=datetime.now() - timedelta(days=random.randint(0, 5)),
            platform=random.choice(['Web', 'iOS', 'Android']),
            explore_name='Chrome',
            explore_version='114.0',
        )


def main():
    print('Generating full random test data...')
    with transaction.atomic():
        semester_types = create_semesters()
        persons, teachers, organizations, org_types, org_tags = create_persons_and_orgs()
        users = [person.person_id for person in persons] + [org.organization_id for org in organizations]
        create_generic_records(users)
        create_help_wishes_modify_records(users)
        comment_base = create_comment_and_notification(users)
        activities = create_activity_data(persons, organizations, teachers)
        create_course_data(persons, organizations)
        create_academic_data(persons, users)
        create_prize_pool_data(users, activities)
        create_appointment_data(users)
        create_dormitory_data(users)
        create_library_data(users)
        create_record_logs(users)
        ModifyOrganization.objects.create(
            oname='测试组织申请',
            otype=random.choice(org_types),
            introduction=fake.text(max_nb_chars=80),
            application=fake.text(max_nb_chars=100),
            pos=random.choice(users),
            status=ModifyOrganization.Status.PENDING,
            tags='测试',
        )
        ModifyPosition.objects.create(
            person=random.choice(persons),
            org=random.choice(organizations),
            pos=random.randint(1, 3),
            reason=fake.text(max_nb_chars=80),
            apply_type=random.choice([t[0] for t in ModifyPosition.ApplyType.choices]),
            status=ModifyPosition.Status.PENDING,
        )
    credentials_path = os.path.join(PROJECT_ROOT, 'scripts', 'generated_credentials.txt')
    with open(credentials_path, 'w', encoding='utf-8') as cred_file:
        cred_file.write('username,password,utype\n')
        for username, password, utype in CREATED_CREDENTIALS:
            cred_file.write(f'{username},{password},{utype}\n')

    print('Done!')
    print(f'Created {len(users)} users, {len(persons)} natural persons, {len(organizations)} organizations.')
    print(f'Generated credential list saved to: {credentials_path}')


if __name__ == '__main__':
    main()
