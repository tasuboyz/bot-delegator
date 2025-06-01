from collections import defaultdict
from datetime import datetime, timezone
from flask import Flask

published_posts = set()

last_check_time = defaultdict(lambda: datetime.now(timezone.utc))

local_data_list = []