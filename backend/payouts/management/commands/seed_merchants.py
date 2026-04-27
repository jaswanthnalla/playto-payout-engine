from django.core.management.base import BaseCommand

from payouts.models import LedgerEntry, Merchant


class Command(BaseCommand):
    help = 'Seeds 3 merchants with credit history'

    def handle(self, *args, **options):
        merchants = [
            {
                'name': 'Arjun Designs',
                'email': 'arjun@arjundesigns.in',
                'bank_accounts': [
                    {'id': 'acc_arjun_1', 'bank': 'HDFC', 'account': '****1234'}
                ],
                'credits': [500000, 250000, 750000],  # ₹15,000
            },
            {
                'name': 'Priya Dev Studio',
                'email': 'priya@priyadev.io',
                'bank_accounts': [
                    {'id': 'acc_priya_1', 'bank': 'ICICI', 'account': '****5678'}
                ],
                'credits': [1000000, 500000],  # ₹15,000
            },
            {
                'name': 'Mumbai SEO Agency',
                'email': 'ops@mumbaisco.com',
                'bank_accounts': [
                    {'id': 'acc_mumbai_1', 'bank': 'Axis', 'account': '****9012'}
                ],
                'credits': [2000000, 1500000, 500000],  # ₹40,000
            },
        ]

        for data in merchants:
            merchant, created = Merchant.objects.get_or_create(
                email=data['email'],
                defaults={
                    'name': data['name'],
                    'bank_accounts': data['bank_accounts'],
                },
            )
            if created:
                for i, amount in enumerate(data['credits']):
                    LedgerEntry.objects.create(
                        merchant=merchant,
                        amount=amount,
                        entry_type='CREDIT',
                        description=f'Customer payment #{i + 1}',
                    )
                self.stdout.write(self.style.SUCCESS(f"Created: {merchant.name} ({merchant.id})"))
            else:
                self.stdout.write(f"Exists: {merchant.name} ({merchant.id})")

        self.stdout.write(self.style.SUCCESS('Seed complete.'))
