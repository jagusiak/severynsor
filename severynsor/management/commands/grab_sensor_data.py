from django.core.management.base import BaseCommand
from severynsor.models import SensorRetriever

class Command(BaseCommand):
    help = 'Grabs sensor data from all configured retrievers'

    def handle(self, *args, **options):
        retrievers = SensorRetriever.objects.all()
        count = 0
        self.stdout.write(self.style.NOTICE(f'Checking {retrievers.count()} retrievers...'))
        
        for retriever in retrievers:
            if retriever.should_run():
                self.stdout.write(self.style.NOTICE(f'Retriever {retriever} should run. Grabbing data...'))
                try:
                    retriever.grab_data()
                    count += 1
                except NotImplementedError:
                    self.stdout.write(self.style.WARNING(f'Retriever {retriever} has not implemented grab_data().'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error running retriever {retriever}: {e}'))
            else:
                self.stdout.write(self.style.NOTICE(f'Retriever {retriever} skipped (already ran for this period).'))
        
        self.stdout.write(self.style.SUCCESS(f'Successfully grabbed data for {count} retrievers.'))
