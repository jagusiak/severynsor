from django.core.management.base import BaseCommand
from severynsor.models import SensorRetriever
from severynsor.models.log import ActivityLog
from django.utils import timezone
import traceback

class Command(BaseCommand):
    help = 'Grabs sensor data from all configured retrievers'

    def handle(self, *args, **options):
        retrievers = SensorRetriever.objects.all()
        count = 0
        self.stdout.write(self.style.NOTICE(f'Checking {retrievers.count()} retrievers...'))
        
        for retriever in retrievers:
            if retriever.should_run():
                self.stdout.write(self.style.NOTICE(f'Retriever {retriever} should run. Grabbing data...'))
                start_time = timezone.now()
                try:
                    retriever.grab_data()
                    count += 1
                    ActivityLog.objects.create(
                        type=ActivityLog.RETRIEVER,
                        sensor=retriever.sensor,
                        retriever=retriever,
                        success=True,
                        timestamp=start_time,
                        duration=(timezone.now() - start_time).total_seconds()
                    )
                except NotImplementedError:
                    self.stdout.write(self.style.WARNING(f'Retriever {retriever} has not implemented grab_data().'))
                    # We don't log NotImplementedError as a failure if it's the base class, 
                    # but actually it is a failure of configuration if it's meant to run.
                    ActivityLog.objects.create(
                        type=ActivityLog.RETRIEVER,
                        sensor=retriever.sensor,
                        retriever=retriever,
                        success=False,
                        error_message="Retriever has not implemented grab_data().",
                        timestamp=start_time,
                        duration=(timezone.now() - start_time).total_seconds()
                    )
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error running retriever {retriever}: {e}'))
                    ActivityLog.objects.create(
                        type=ActivityLog.RETRIEVER,
                        sensor=retriever.sensor,
                        retriever=retriever,
                        success=False,
                        error_message=f"{str(e)}\n{traceback.format_exc()}",
                        timestamp=start_time,
                        duration=(timezone.now() - start_time).total_seconds()
                    )
            else:
                self.stdout.write(self.style.NOTICE(f'Retriever {retriever} skipped (already ran for this period).'))
        
        self.stdout.write(self.style.SUCCESS(f'Successfully grabbed data for {count} retrievers.'))
