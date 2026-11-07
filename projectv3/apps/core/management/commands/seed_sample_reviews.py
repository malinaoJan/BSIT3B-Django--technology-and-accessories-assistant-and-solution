import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.models import Accessory, Product, Review

SAMPLE_USER_PREFIX = 'techfix_sample_'

REVIEWERS = [
    ('Maya', 'R.'), ('Liam', 'C.'), ('Sofia', 'M.'), ('Noah', 'T.'),
    ('Ava', 'G.'), ('Ethan', 'P.'), ('Isla', 'D.'), ('Lucas', 'B.'),
    ('Chloe', 'S.'), ('Mateo', 'V.'), ('Nina', 'F.'), ('Leo', 'A.'),
    ('Grace', 'H.'), ('Kai', 'N.'), ('Elena', 'J.'), ('Owen', 'L.'),
    ('Ruby', 'W.'), ('Adam', 'K.'), ('Zoe', 'Q.'), ('Miles', 'E.'),
    ('Lara', 'I.'), ('Jonah', 'U.'), ('Mia', 'O.'), ('Theo', 'Y.'),
]

TITLES = {
    5: [
        'Excellent choice', 'Very happy with this', 'Better than expected',
        'Great everyday pick', 'Would buy again', 'Really impressed',
    ],
    4: [
        'Good value', 'Happy with it so far', 'Solid purchase',
        'Does the job well', 'Pleased with this', 'Recommended',
    ],
    3: [
        'Decent for the price', 'Works fine', 'Okay overall',
        'A fair choice', 'Does what it says', 'Middle of the road',
    ],
    2: [
        'A few letdowns', 'Mixed experience', 'Could be better',
        'Not quite for me', 'Expected more',
    ],
    1: [
        'Disappointed', 'Not what I hoped', 'Would not recommend',
    ],
}

OPENERS = {
    5: [
        "I've been using the {name} for a few weeks and it has been excellent.",
        "The {name} has exceeded my expectations so far.",
        "After a month with the {name}, I am very happy with it.",
        "I bought the {name} for everyday use and it has been great.",
        "This was a worthwhile upgrade, and the {name} has been reliable from day one.",
    ],
    4: [
        "The {name} has been a solid purchase so far.",
        "I have used the {name} regularly and it does what I need.",
        "I picked up the {name} recently and I am pleased overall.",
        "For the price, the {name} has been a good buy.",
        "The {name} arrived on time and has worked well since.",
    ],
    3: [
        "The {name} is okay for everyday use.",
        "I have mixed feelings about the {name}.",
        "The {name} does the basics, though it has a few rough edges.",
        "My experience with the {name} has been average.",
        "The {name} is serviceable, but it did not wow me.",
    ],
    2: [
        "I had higher hopes for the {name}.",
        "The {name} has some good points, but it also has letdowns.",
        "I have not been fully satisfied with the {name}.",
        "The {name} works, but I expected better.",
        "My experience with the {name} has been uneven.",
    ],
    1: [
        "The {name} did not work out for me.",
        "I regret buying the {name}.",
        "The {name} fell short of what was described.",
        "I had a poor experience with the {name}.",
        "The {name} was not what I expected.",
    ],
}

CLOSERS = {
    5: [
        'Would recommend it to anyone looking for a dependable option.',
        'I would happily buy this again.',
        'It has earned a permanent place in my setup.',
        'Overall, a great purchase.',
        'Two thumbs up from me.',
    ],
    4: [
        'Overall, I am happy with the value.',
        'I would recommend it with minor caveats.',
        'A good option if you want something dependable.',
        'No regrets so far.',
        'Worth considering if the price fits your budget.',
    ],
    3: [
        'It gets the job done, but I would not call it exceptional.',
        'Fine for basic needs, though I would compare alternatives.',
        'An acceptable choice if your expectations are modest.',
        'It is okay, but nothing stands out.',
        'I would only recommend it on a discount.',
    ],
    2: [
        'I would suggest comparing other options first.',
        'It might suit light use, but it was not right for me.',
        'I expected more for the price.',
        'Not a bad product, but not a great one either.',
        'I would think twice before buying it again.',
    ],
    1: [
        'I will be looking for a replacement.',
        'I cannot recommend it based on my experience.',
        'It was a frustrating purchase.',
        'I would avoid it unless the price is very low.',
        'This one missed the mark for me.',
    ],
}

KIND_LINES = {
    'phone': {
        'positive': 'Calls are clear, everyday apps run smoothly, and the camera handles my usual photos well.',
        'neutral': 'It covers the basics, though heavier apps can slow it down and the speakers are average.',
        'negative': 'It lags with demanding apps and the battery drains faster than I expected.',
    },
    'laptop': {
        'positive': 'It starts up quickly, the keyboard is comfortable, and it handles my daily work and video calls without fuss.',
        'neutral': 'It manages light work fine, but it gets warm under load and I wish it had more ports.',
        'negative': 'It slows down with several apps open and the battery does not last as long as I hoped.',
    },
    'desktop': {
        'positive': 'It runs my daily programs smoothly and stays reasonably quiet.',
        'neutral': 'It handles office work well, but I would not push it with heavy games.',
        'negative': 'It struggles with demanding software and the fans get loud under load.',
    },
    'tablet': {
        'positive': 'The screen is bright, apps open quickly, and it is comfortable to hold for reading and streaming.',
        'neutral': 'It works for browsing and videos, though the speakers could be better.',
        'negative': 'It feels slow with several apps open and the battery drops quickly with video.',
    },
    'handheld': {
        'positive': 'Games run smoothly and the controls feel comfortable during longer sessions.',
        'neutral': 'It handles casual games well, but the screen and battery are only average.',
        'negative': 'It gets warm and the battery drains quickly during longer play sessions.',
    },
    'gamepad': {
        'positive': 'The buttons feel responsive and it paired with my device without any trouble.',
        'neutral': 'It works for most games, though the grip takes some getting used to.',
        'negative': 'The sticks felt a little loose and the connection dropped a few times.',
    },
    'monitor': {
        'positive': 'The picture is sharp, colours look good, and text is easy to read for long work sessions.',
        'neutral': 'It displays fine, but I had to adjust the settings and the built-in speakers are weak.',
        'negative': 'The viewing angles are limited and the stand feels less sturdy than I expected.',
    },
    'tv': {
        'positive': 'The picture is clear and bright, and streaming apps load without delay.',
        'neutral': 'It handles everyday viewing well, though the sound is a bit thin.',
        'negative': 'The smart interface feels sluggish and the picture needs a lot of adjustment.',
    },
    'camera': {
        'positive': 'Photos come out sharp, autofocus is quick, and the controls are easy to learn.',
        'neutral': 'It takes good photos in good light, though low-light shots need some patience.',
        'negative': 'The autofocus hunted in low light and the battery ran out faster than expected.',
    },
    'webcam': {
        'positive': 'Video calls look clear, setup was instant, and the microphone is good enough for meetings.',
        'neutral': 'It works for calls, though the image gets noisy in dim rooms.',
        'negative': 'The image is soft and the mount does not hold the angle very well.',
    },
    'lens': {
        'positive': 'Images are sharp, focusing is smooth, and it feels solid on the camera.',
        'neutral': 'It produces good results, though it is heavier than I expected.',
        'negative': 'Focusing was inconsistent and the images looked soft at wider apertures.',
    },
    'projector': {
        'positive': 'The image is bright enough for a dim room and setup was straightforward.',
        'neutral': 'It works for movie nights, but the built-in speaker is not very loud.',
        'negative': 'The picture looks washed out in anything but a dark room and the fan is noisy.',
    },
    'printer': {
        'positive': 'Print quality is clean, wireless setup was easy, and it has been reliable so far.',
        'neutral': 'It prints fine for documents, though it is slower than I expected.',
        'negative': 'It jams occasionally and the ink consumption is higher than I would like.',
    },
    'scanner': {
        'positive': 'Scans are clear, the software was easy to set up, and it handles documents quickly.',
        'neutral': 'It scans fine, though the included software feels dated.',
        'negative': 'The scans needed a lot of cleanup and the feeder occasionally pulled pages crooked.',
    },
    'ink': {
        'positive': 'Prints come out clean and the colours have stayed consistent.',
        'neutral': 'It does the job, though I wish the yield were a little higher.',
        'negative': 'The output was uneven and I had to clean the print head more than once.',
    },
    'router': {
        'positive': 'Setup was quick, the signal reaches the whole house, and the connection has been stable.',
        'neutral': 'It covers my apartment fine, though the app could be easier to use.',
        'negative': 'The signal drops in the far rooms and I have had to reboot it a few times.',
    },
    'watch': {
        'positive': 'The screen is easy to read, notifications arrive reliably, and the battery lasts through the day.',
        'neutral': 'It tracks the basics well, though some features feel limited without a phone nearby.',
        'negative': 'The battery barely makes it through a full day and the sensors are inconsistent.',
    },
    'strap': {
        'positive': 'The strap fits comfortably and the colour matches the photos.',
        'neutral': 'It is comfortable enough, though the material feels basic.',
        'negative': 'The fit was awkward and it started showing wear quickly.',
    },
    'earbuds': {
        'positive': 'Sound is clear, the fit is comfortable, and pairing has been reliable.',
        'neutral': 'They sound fine for music and calls, though the bass is modest.',
        'negative': 'The connection cuts out occasionally and the fit is not secure for me.',
    },
    'headphone': {
        'positive': 'The sound is full and clear, the padding is comfortable, and battery life is good.',
        'neutral': 'They sound decent for everyday listening, though they clamp a little tightly.',
        'negative': 'The earcups get uncomfortable after an hour and the sound feels muddy.',
    },
    'headset': {
        'positive': 'The microphone is clear, the fit is comfortable, and game audio sounds immersive.',
        'neutral': 'It works well for calls and casual gaming, though the software is fiddly.',
        'negative': 'The microphone picked up background noise and the headband felt tight.',
    },
    'speaker': {
        'positive': 'The sound is loud and clear, pairing is quick, and it feels well built.',
        'neutral': 'It sounds good at moderate volume, though the bass drops off when turned up.',
        'negative': 'The sound distorts at higher volumes and the battery does not last as long as advertised.',
    },
    'microphone': {
        'positive': 'The audio sounds clear and warm, and setup with my computer was simple.',
        'neutral': 'It records fine for calls and streams, though it picks up some room noise.',
        'negative': 'There was a constant hiss in the recordings and the mount felt flimsy.',
    },
    'powerbank': {
        'positive': 'It charges my phone quickly, holds its charge well, and feels solidly built.',
        'neutral': 'It does the job, though it is heavier than I expected.',
        'negative': 'The capacity seems lower than advertised and it gets warm while charging.',
    },
    'battery': {
        'positive': 'It fits perfectly and holds a charge as well as the original.',
        'neutral': 'It works, though the battery life is slightly shorter than the original.',
        'negative': 'It drains quickly and the device sometimes reports an unknown battery.',
    },
    'charger': {
        'positive': 'Charging is fast, the build feels solid, and it does not get overly warm.',
        'neutral': 'It charges at a reasonable speed, though it is bulkier than I expected.',
        'negative': 'It charges slowly and sometimes stops charging when the cable moves.',
    },
    'cable': {
        'positive': 'The cable feels sturdy, the connectors fit snugly, and charging is consistent.',
        'neutral': 'It works fine, though the braiding attracts lint.',
        'negative': 'The connection cuts out when the cable is bent and the plug feels loose.',
    },
    'hub': {
        'positive': 'All the ports work, the connection is stable, and it is compact enough to carry.',
        'neutral': 'It handles my basic peripherals, though it gets warm with several devices attached.',
        'negative': 'One of the ports stopped working and the hub occasionally disconnects.',
    },
    'stand': {
        'positive': 'It holds the device at a comfortable angle and feels stable on the desk.',
        'neutral': 'It does the job, though the hinges are stiffer than I would like.',
        'negative': 'It wobbles when I type and the rubber pads came loose.',
    },
    'case': {
        'positive': 'The fit is precise, the material feels durable, and it protects the device well.',
        'neutral': 'It fits well enough, though the buttons are a little stiff.',
        'negative': 'It does not line up perfectly with the ports and the material feels cheap.',
    },
    'screenprotector': {
        'positive': 'Installation was easy, the surface feels smooth, and the screen stays clear.',
        'neutral': 'It fits fine, though a couple of bubbles remained after installation.',
        'negative': 'It cracked within a week and the edges did not sit flat.',
    },
    'bag': {
        'positive': 'There is plenty of room, the straps are comfortable, and the padding feels protective.',
        'neutral': 'It carries my gear fine, though the main compartment could use more organization.',
        'negative': 'The stitching started coming loose and the shoulder strap is uncomfortable.',
    },
    'keyboard': {
        'positive': 'The keys feel responsive, typing is comfortable, and the connection has been stable.',
        'neutral': 'It types fine, though the key travel took some getting used to.',
        'negative': 'Some keys started double-registering and the frame flexes under pressure.',
    },
    'mouse': {
        'positive': 'The sensor tracks accurately, it is comfortable to hold, and the battery lasts well.',
        'neutral': 'It works well for everyday use, though it is a little small for my hand.',
        'negative': 'The scroll wheel became erratic and the cursor occasionally stutters.',
    },
    'storage': {
        'positive': 'Transfer speeds are good, it has been reliable, and it is easy to carry.',
        'neutral': 'It stores files fine, though it runs warm during large transfers.',
        'negative': 'The speeds dropped sharply after a few uses and it occasionally disconnects.',
    },
    'pen': {
        'positive': 'It writes smoothly, the pressure response feels natural, and it pairs quickly.',
        'neutral': 'It works well for notes, though the tip is slightly harder than I prefer.',
        'negative': 'The pen loses connection intermittently and the tip wore down quickly.',
    },
    'tag': {
        'positive': 'Setup was quick and it has helped me find my keys more than once.',
        'neutral': 'It works as a basic tracker, though the range is shorter than advertised.',
        'negative': 'The connection is unreliable and the battery needed replacing sooner than expected.',
    },
    'light': {
        'positive': 'The light is bright and adjustable, and it makes a big difference on video calls.',
        'neutral': 'It works well, though the mount feels a little plasticky.',
        'negative': 'The brightness is uneven and the controls are awkward to reach.',
    },
    'scale': {
        'positive': 'It is consistent, easy to set up, and the app syncing works reliably.',
        'neutral': 'It measures the basics fine, though the app could be clearer.',
        'negative': 'The readings vary between uses and the app often fails to sync.',
    },
    'default': {
        'positive': 'It works exactly as described, feels well made, and has been reliable so far.',
        'neutral': 'It does the job, though the finish and features are fairly basic.',
        'negative': 'It works, but the build and fit were not what I hoped for.',
    },
}


def _rating(rng):
    return rng.choices([5, 4, 3, 2, 1], weights=[38, 34, 19, 6, 3], k=1)[0]


def _candidates(item, rng, total=24):
    lines = KIND_LINES.get(item.kind, KIND_LINES['default'])
    candidates = []
    seen = set()
    attempts = 0
    while len(candidates) < total and attempts < total * 8:
        attempts += 1
        rating = _rating(rng)
        title = rng.choice(TITLES[rating])
        if rating >= 4:
            tone = 'positive'
            if rating == 4 and rng.random() < 0.2:
                tone = 'neutral'
        elif rating == 3:
            tone = 'neutral'
        else:
            tone = 'negative'
        opener = rng.choice(OPENERS[rating]).replace('{name}', item.name)
        comment = ' '.join([opener, lines[tone], rng.choice(CLOSERS[rating])])
        key = (title, comment)
        if key in seen:
            continue
        seen.add(key)
        candidates.append((rating, title, comment))
    return candidates


def _sample_users():
    user_model = get_user_model()
    reviewers = []
    for index, (first_name, last_name) in enumerate(REVIEWERS, start=1):
        username = f'{SAMPLE_USER_PREFIX}{index:02d}'
        user, created = user_model.objects.get_or_create(
            username=username,
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'email': f'{username}@example.invalid',
                'is_active': False,
            },
        )
        changed = []
        if user.first_name != first_name:
            user.first_name = first_name
            changed.append('first_name')
        if user.last_name != last_name:
            user.last_name = last_name
            changed.append('last_name')
        if user.is_active:
            user.is_active = False
            changed.append('is_active')
        if created or user.has_usable_password():
            user.set_unusable_password()
            changed.append('password')
        if changed:
            user.save(update_fields=changed)
        reviewers.append(user)
    return reviewers


class Command(BaseCommand):
    help = 'Create clearly labeled sample reviews for every product and accessory.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--min-reviews',
            type=int,
            default=3,
            help='Minimum number of sample reviews per item (default: 3).',
        )
        parser.add_argument(
            '--max-reviews',
            type=int,
            default=5,
            help='Maximum number of sample reviews per item (default: 5).',
        )
        parser.add_argument(
            '--seed',
            type=int,
            default=2026,
            help='Random seed for repeatable demo content (default: 2026).',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Remove all sample reviews and exit.',
        )
        parser.add_argument(
            '--category',
            action='append',
            default=[],
            help='Limit to products/accessories in this category (repeatable).',
        )
        parser.add_argument(
            '--missing-only',
            action='store_true',
            help='Only add reviews to items that do not have any reviews yet.',
        )

    def handle(self, *args, **options):
        if options['clear']:
            removed, _ = Review.objects.filter(is_sample=True).delete()
            self.stdout.write(self.style.SUCCESS(f'Removed {removed} sample reviews.'))
            return

        min_reviews = options['min_reviews']
        max_reviews = options['max_reviews']
        if min_reviews < 1:
            raise CommandError('--min-reviews must be at least 1.')
        if max_reviews < min_reviews:
            raise CommandError('--max-reviews must be greater than or equal to --min-reviews.')

        rng = random.Random(options['seed'])
        products_qs = Product.objects.select_related('category').order_by('pk')
        accessories_qs = Accessory.objects.select_related('category').order_by('pk')
        if options['category']:
            products_qs = products_qs.filter(
                category__name__in=options['category']
            )
            accessories_qs = accessories_qs.filter(
                category__name__in=options['category']
            )
        products = list(products_qs)
        accessories = list(accessories_qs)
        if options['missing_only']:
            reviewed_products = set(
                Review.objects.exclude(product__isnull=True)
                .values_list('product_id', flat=True)
            )
            reviewed_accessories = set(
                Review.objects.exclude(accessory__isnull=True)
                .values_list('accessory_id', flat=True)
            )
            products = [
                item for item in products if item.pk not in reviewed_products
            ]
            accessories = [
                item for item in accessories
                if item.pk not in reviewed_accessories
            ]
        items = [(item, True) for item in products]
        items.extend((item, False) for item in accessories)

        if not items:
            if options['missing_only']:
                self.stdout.write(
                    self.style.SUCCESS('Every selected item already has reviews.')
                )
                return
            raise CommandError('There are no products or accessories to review.')

        now = timezone.now()
        with transaction.atomic():
            if not options['missing_only']:
                Review.objects.filter(is_sample=True).filter(
                    Q(product__in=products) | Q(accessory__in=accessories)
                ).delete()
            reviewers = _sample_users()
            reviews = []
            dates = []

            for item, is_product in items:
                candidates = _candidates(item, rng)
                count = min(
                    rng.randint(min_reviews, max_reviews),
                    len(reviewers),
                    len(candidates),
                )
                chosen = rng.sample(candidates, count)
                for reviewer, (rating, title, comment) in zip(
                    rng.sample(reviewers, count), chosen
                ):
                    review = Review(
                        product=item if is_product else None,
                        accessory=None if is_product else item,
                        user=reviewer,
                        rating=rating,
                        title=title,
                        comment=comment,
                        is_sample=True,
                    )
                    reviews.append(review)
                    dates.append(
                        now - timedelta(
                            days=rng.randint(2, 540),
                            hours=rng.randint(0, 23),
                            minutes=rng.randint(0, 59),
                        )
                    )

            Review.objects.bulk_create(reviews, batch_size=500)
            for review, created_at in zip(reviews, dates):
                review.created_at = created_at
            Review.objects.bulk_update(reviews, ['created_at'], batch_size=500)

        self.stdout.write(
            self.style.SUCCESS(
                f'Created {len(reviews)} labeled sample reviews for '
                f'{len(products)} products and {len(accessories)} accessories.'
            )
        )
