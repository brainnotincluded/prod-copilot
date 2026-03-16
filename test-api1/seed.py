#!/usr/bin/env python3
"""Seed the marketing API SQLite database with realistic test data."""

import sqlite3
import json
import random
import os
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "marketing.db")

FIRST_NAMES = [
    "Alexander", "Maria", "Dmitry", "Anna", "Sergei", "Elena", "Ivan", "Olga",
    "Nikolai", "Tatiana", "Andrei", "Natalia", "Pavel", "Ekaterina", "Mikhail",
    "Irina", "Alexei", "Svetlana", "Roman", "Julia", "Viktor", "Daria",
    "Konstantin", "Anastasia", "Evgeny", "Ksenia", "Boris", "Polina", "Oleg",
    "Vera", "Artem", "Alina", "Vladislav", "Sofia", "Maxim", "Lidia",
    "Denis", "Marina", "Timofei", "Galina", "Igor", "Valentina", "Kirill",
    "Larisa", "Georgy", "Nadezhda", "Stepan", "Tamara", "Fedor", "Lyubov",
]

LAST_NAMES = [
    "Ivanov", "Petrov", "Sidorov", "Kuznetsov", "Popov", "Sokolov", "Lebedev",
    "Kozlov", "Novikov", "Morozov", "Volkov", "Soloviev", "Vasiliev", "Zaytsev",
    "Pavlov", "Semenov", "Golubev", "Vinogradov", "Bogdanov", "Vorobyev",
    "Fedorov", "Mikhailov", "Belyaev", "Tarasov", "Belov", "Komarov",
    "Orlov", "Kiselev", "Makarov", "Andreev", "Kovalev", "Ilyin", "Gusev",
    "Titov", "Kuzmin", "Kudryavtsev", "Baranov", "Kulikov", "Alekseev", "Stepanov",
]

SEGMENTS_DATA = [
    {
        "name": "Premium",
        "description": "High-value customers with average check above 5000 RUB. These users represent the top spending tier and are ideal for premium offers.",
        "criteria": {"avg_check_min": 5000, "status": "active"},
        "estimated_size": 85,
        "status": "active",
    },
    {
        "name": "Inactive 60+ days",
        "description": "Users who have not made any purchases or interactions in the last 60 days. Targeted for re-engagement campaigns.",
        "criteria": {"last_active_days_min": 60, "status": "active"},
        "estimated_size": 120,
        "status": "active",
    },
    {
        "name": "High Average Check",
        "description": "Users whose average purchase amount is in the top 25th percentile. Suitable for upselling and cross-selling.",
        "criteria": {"avg_check_min": 3000, "avg_check_max": 15000},
        "estimated_size": 150,
        "status": "active",
    },
    {
        "name": "New Users (last 30 days)",
        "description": "Recently registered users within the last 30 days. Focus on onboarding flows and welcome offers.",
        "criteria": {"registered_days_max": 30, "status": "active"},
        "estimated_size": 65,
        "status": "active",
    },
    {
        "name": "Frequent Buyers",
        "description": "Users with 10 or more purchases in total. Loyal customer base suitable for loyalty rewards and referral programs.",
        "criteria": {"total_purchases_min": 10},
        "estimated_size": 95,
        "status": "active",
    },
]

PUSH_TEMPLATES = [
    {
        "name": "Flash Sale",
        "title_template": "Flash Sale: {discount}% off!",
        "body_template": "Don't miss out! Get {discount}% off on {category} items. Offer ends in {hours} hours.",
        "category": "promotion",
    },
    {
        "name": "Cart Abandonment",
        "title_template": "You left something behind!",
        "body_template": "Hi {name}, your cart is waiting. Complete your purchase of {item} and save {discount}%.",
        "category": "retention",
    },
    {
        "name": "Welcome Offer",
        "title_template": "Welcome to {brand}!",
        "body_template": "Hi {name}, thanks for joining! Here's {discount}% off your first order. Use code: {code}.",
        "category": "onboarding",
    },
    {
        "name": "Loyalty Reward",
        "title_template": "You've earned a reward!",
        "body_template": "Congrats {name}! You've earned {points} bonus points. Redeem them on your next purchase.",
        "category": "loyalty",
    },
    {
        "name": "Re-engagement",
        "title_template": "We miss you, {name}!",
        "body_template": "It's been a while! Come back and discover what's new. Here's {discount}% off to welcome you back.",
        "category": "reactivation",
    },
]


def create_tables(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS segments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            criteria TEXT NOT NULL,
            estimated_size INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audiences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            segment_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            size INTEGER DEFAULT 0,
            status TEXT DEFAULT 'ready',
            created_at TEXT NOT NULL,
            filters TEXT,
            FOREIGN KEY (segment_id) REFERENCES segments(id)
        );

        CREATE TABLE IF NOT EXISTS audience_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audience_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (audience_id) REFERENCES audiences(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audience_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            channel TEXT NOT NULL DEFAULT 'push',
            status TEXT DEFAULT 'draft',
            message_variants TEXT,
            created_at TEXT NOT NULL,
            scheduled_at TEXT,
            FOREIGN KEY (audience_id) REFERENCES audiences(id)
        );

        CREATE TABLE IF NOT EXISTS push_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            title_template TEXT NOT NULL,
            body_template TEXT NOT NULL,
            category TEXT
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            segment TEXT,
            avg_check REAL DEFAULT 0,
            last_active TEXT,
            total_purchases INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active'
        );

        CREATE TABLE IF NOT EXISTS campaign_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            conversions INTEGER DEFAULT 0,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
        );
    """)
    conn.commit()


def seed_users(conn: sqlite3.Connection, count: int = 500):
    cur = conn.cursor()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    users = []
    emails_seen = set()

    segment_names = ["Premium", "Inactive 60+ days", "High Average Check",
                     "New Users (last 30 days)", "Frequent Buyers"]

    for i in range(count):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        name = f"{first} {last}"

        base_email = f"{first.lower()}.{last.lower()}"
        email = f"{base_email}@example.com"
        suffix = 1
        while email in emails_seen:
            email = f"{base_email}{suffix}@example.com"
            suffix += 1
        emails_seen.add(email)

        segment = random.choice(segment_names)
        avg_check = round(random.uniform(100, 15000), 2)
        days_ago = random.randint(1, 120)
        last_active = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        total_purchases = random.randint(0, 50)
        status = "active" if days_ago < 90 else random.choice(["active", "inactive"])

        # Adjust data to match segment semantics
        if segment == "Premium":
            avg_check = round(random.uniform(5000, 15000), 2)
            status = "active"
        elif segment == "Inactive 60+ days":
            days_ago = random.randint(60, 120)
            last_active = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        elif segment == "High Average Check":
            avg_check = round(random.uniform(3000, 15000), 2)
        elif segment == "New Users (last 30 days)":
            days_ago = random.randint(1, 30)
            last_active = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            total_purchases = random.randint(0, 5)
            status = "active"
        elif segment == "Frequent Buyers":
            total_purchases = random.randint(10, 50)

        users.append((name, email, segment, avg_check, last_active, total_purchases, status))

    cur.executemany(
        "INSERT INTO users (name, email, segment, avg_check, last_active, total_purchases, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        users,
    )
    conn.commit()
    return len(users)


def seed_segments(conn: sqlite3.Connection):
    cur = conn.cursor()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for seg in SEGMENTS_DATA:
        created = (now - timedelta(days=random.randint(5, 60))).isoformat()
        cur.execute(
            "INSERT INTO segments (name, description, criteria, estimated_size, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (seg["name"], seg["description"], json.dumps(seg["criteria"]),
             seg["estimated_size"], seg["status"], created),
        )
    conn.commit()


def seed_audiences(conn: sqlite3.Connection):
    cur = conn.cursor()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    audiences_data = [
        {"segment_id": 1, "name": "Premium Q1 2026", "filters": {"region": "all"}},
        {"segment_id": 2, "name": "Re-engagement March", "filters": {"channel": "push"}},
        {"segment_id": 5, "name": "Loyal Customers Spring", "filters": {"min_purchases": 15}},
    ]

    for aud in audiences_data:
        created = (now - timedelta(days=random.randint(1, 15))).isoformat()
        # Get matching users for this audience
        seg = cur.execute("SELECT criteria FROM segments WHERE id = ?", (aud["segment_id"],)).fetchone()
        criteria = json.loads(seg[0]) if seg else {}

        # Build a query to find matching users
        conditions = ["1=1"]
        if "avg_check_min" in criteria:
            conditions.append(f"avg_check >= {criteria['avg_check_min']}")
        if "avg_check_max" in criteria:
            conditions.append(f"avg_check <= {criteria['avg_check_max']}")
        if "total_purchases_min" in criteria:
            conditions.append(f"total_purchases >= {criteria['total_purchases_min']}")

        query = f"SELECT id FROM users WHERE {' AND '.join(conditions)}"
        matching_users = cur.execute(query).fetchall()
        size = len(matching_users)

        cur.execute(
            "INSERT INTO audiences (segment_id, name, size, status, created_at, filters) "
            "VALUES (?, ?, ?, 'ready', ?, ?)",
            (aud["segment_id"], aud["name"], size, created, json.dumps(aud["filters"])),
        )
        audience_id = cur.lastrowid

        # Add members (limit to keep it reasonable)
        for user_row in matching_users[:200]:
            cur.execute(
                "INSERT INTO audience_members (audience_id, user_id) VALUES (?, ?)",
                (audience_id, user_row[0]),
            )

    conn.commit()


def seed_campaigns(conn: sqlite3.Connection):
    cur = conn.cursor()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    campaigns_data = [
        {
            "audience_id": 1,
            "title": "Premium Spring Promo",
            "channel": "push",
            "status": "completed",
            "message_variants": [
                {"variant": "A", "title": "Exclusive Spring Deals!", "body": "Premium members get 20% off all spring items.", "weight": 50},
                {"variant": "B", "title": "Your VIP Spring Offer", "body": "As a valued customer, enjoy 25% off this weekend.", "weight": 50},
            ],
            "scheduled_at": (now - timedelta(days=10)).isoformat(),
        },
        {
            "audience_id": 2,
            "title": "Come Back & Save",
            "channel": "push",
            "status": "draft",
            "message_variants": [
                {"variant": "A", "title": "We Miss You!", "body": "It's been a while! Here's 15% off to welcome you back.", "weight": 50},
                {"variant": "B", "title": "Still Thinking About It?", "body": "Your favorites are waiting. Get 15% off today only.", "weight": 50},
                {"variant": "C", "title": "A Gift for You", "body": "Come back and enjoy free shipping + 10% off your next order.", "weight": 0},
            ],
            "scheduled_at": None,
        },
    ]

    for camp in campaigns_data:
        created = (now - timedelta(days=random.randint(3, 20))).isoformat()
        cur.execute(
            "INSERT INTO campaigns (audience_id, title, channel, status, message_variants, created_at, scheduled_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (camp["audience_id"], camp["title"], camp["channel"], camp["status"],
             json.dumps(camp["message_variants"]), created, camp["scheduled_at"]),
        )

    conn.commit()


def seed_campaign_metrics(conn: sqlite3.Connection):
    """Seed 7 days of metrics for the completed campaign (id=1)."""
    cur = conn.cursor()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for day_offset in range(7):
        date = (now - timedelta(days=7 - day_offset)).strftime("%Y-%m-%d")
        impressions = random.randint(500, 2000)
        clicks = random.randint(int(impressions * 0.05), int(impressions * 0.25))
        conversions = random.randint(int(clicks * 0.05), int(clicks * 0.30))
        cur.execute(
            "INSERT INTO campaign_metrics (campaign_id, date, impressions, clicks, conversions) "
            "VALUES (?, ?, ?, ?, ?)",
            (1, date, impressions, clicks, conversions),
        )

    conn.commit()


def seed_push_templates(conn: sqlite3.Connection):
    cur = conn.cursor()
    for tpl in PUSH_TEMPLATES:
        cur.execute(
            "INSERT INTO push_templates (name, title_template, body_template, category) "
            "VALUES (?, ?, ?, ?)",
            (tpl["name"], tpl["title_template"], tpl["body_template"], tpl["category"]),
        )
    conn.commit()


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing database: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    print("Creating tables...")
    create_tables(conn)

    print("Seeding users...")
    n = seed_users(conn, count=500)
    print(f"  -> {n} users created")

    print("Seeding segments...")
    seed_segments(conn)
    print(f"  -> {len(SEGMENTS_DATA)} segments created")

    print("Seeding audiences...")
    seed_audiences(conn)
    print("  -> 3 audiences created")

    print("Seeding campaigns...")
    seed_campaigns(conn)
    print("  -> 2 campaigns created")

    print("Seeding campaign metrics...")
    seed_campaign_metrics(conn)
    print("  -> 7 days of metrics created")

    print("Seeding push templates...")
    seed_push_templates(conn)
    print(f"  -> {len(PUSH_TEMPLATES)} templates created")

    conn.close()
    print(f"\nDatabase seeded successfully at {DB_PATH}")


if __name__ == "__main__":
    main()
