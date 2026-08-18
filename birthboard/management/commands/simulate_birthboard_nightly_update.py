from django.core.management.base import BaseCommand, CommandError

from birthboard.jobs import (
	birthboard_nightly_update_0005,
	birthboard_nightly_update_2345,
)


class Command(BaseCommand):
	help = "Simulate birthboard nightly update jobs"

	def add_arguments(self, parser):
		parser.add_argument(
			"--job",
			choices=("2345", "0005", "both"),
			default="both",
			help="Which nightly job to run",
		)

	def handle(self, *args, **options):
		job = options["job"]
		if job == "2345":
			birthboard_nightly_update_2345()
			self.stdout.write(self.style.SUCCESS("birthboard nightly update 23:45 finished"))
			return
		if job == "0005":
			birthboard_nightly_update_0005()
			self.stdout.write(self.style.SUCCESS("birthboard nightly update 00:05 finished"))
			return
		if job == "both":
			birthboard_nightly_update_2345()
			birthboard_nightly_update_0005()
			self.stdout.write(self.style.SUCCESS("birthboard nightly update simulation finished"))
			return
		raise CommandError(f"Unsupported job: {job}")