"""Attach a brand tutorial video to every solution that does not have one.

Each brand folder in the solutions list gets one real, working YouTube tutorial
for that brand's products & accessories. The video thumbnail then shows at the
upper right of the problem description on the solutions page.
"""

import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from apps.core.models import Solution  # noqa: E402

BRAND_VIDEOS = {
    "Huawei": "https://www.youtube.com/watch?v=qzP5XAHm6rU",
    "Infinix": "https://www.youtube.com/watch?v=W9JJfLPMVfM",
    "itel": "https://www.youtube.com/watch?v=-x_oEKPpybw",
    "JBL": "https://www.youtube.com/watch?v=EYwbj7t9PYs",
    "Lenovo": "https://www.youtube.com/watch?v=xhluWwe0K6A",
    "LG": "https://www.youtube.com/watch?v=laXt6cK3bGA",
    "Logitech": "https://www.youtube.com/watch?v=a5a4iAhTaho",
    "Microsoft": "https://www.youtube.com/watch?v=_30bT7QP25Q",
    "MSI": "https://www.youtube.com/watch?v=0urQ3rMTPC4",
    "OnePlus": "https://www.youtube.com/watch?v=XmhL3EFalYo",
    "OPPO": "https://www.youtube.com/watch?v=K6VEu4vnYKI",
    "Razer": "https://www.youtube.com/watch?v=rfH1lwpSEQc",
    "realme": "https://www.youtube.com/watch?v=BJgUAQlEt8g",
    "RedMagic": "https://www.youtube.com/watch?v=q994Dt3vPB4",
    "Samsung": "https://www.youtube.com/watch?v=rtezh9blX78",
    "Sony": "https://www.youtube.com/watch?v=Mqyp3_xZxE4",
    "TECNO": "https://www.youtube.com/watch?v=BQjw7i5WFfk",
    "TP-Link": "https://www.youtube.com/watch?v=3G5iM0V27T4",
    "UGREEN": "https://www.youtube.com/watch?v=p4IAXmLTZo0",
    "vivo": "https://www.youtube.com/watch?v=3zM0HZBH91I",
    "Xiaomi": "https://www.youtube.com/watch?v=U_asqM4SJE8",
}

updated = 0
for brand, url in BRAND_VIDEOS.items():
    queryset = Solution.objects.filter(
        related_product__brand=brand, video_url=""
    )
    count = queryset.update(video_url=url)
    updated += count
    print(f"{brand}: {count} solution(s) linked to {url}")

print(f"total updated: {updated}")
