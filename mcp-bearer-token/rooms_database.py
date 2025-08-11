from typing import List, Dict, Any

ROOMS_DB: List[Dict[str, Any]] = [
    {
        "id": "R005",
        "location": {
            "city": "Bengaluru",
            "area": "Marathahalli",
            "pincode": "560037"
        },
        "rent": 10500,
        "gender_pref": "Any",
        "amenities": [
            "WiFi",
            "Geyser"
        ],
        "description": "Spacious single room in a 2BHK apartment. Close to IT parks.",
        "photo_url": "https://example.com/img5.jpg",
        "posted_by": "user_hash_pqr",
        "date_posted": "2025-08-01",
        "is_active": True,
        "expires_at": "2025-08-31",
        "spots_available": 1
    },
    {
        "id": "R006",
        "location": {
            "city": "Bengaluru",
            "area": "Indiranagar",
            "pincode": "560038"
        },
        "rent": 18000,
        "gender_pref": "Female",
        "amenities": [
            "WiFi",
            "AC",
            "Washing Machine",
            "Balcony"
        ],
        "description": "Luxurious 1BHK near the metro station. Fully furnished.",
        "photo_url": "https://example.com/img6.jpg",
        "posted_by": "user_hash_stu",
        "date_posted": "2025-08-02",
        "is_active": True,
        "expires_at": "2025-09-01",
        "spots_available": 1
    },
    {
        "id": "R007",
        "location": {
            "city": "Pune",
            "area": "Hinjewadi",
            "pincode": "411057"
        },
        "rent": 8500,
        "gender_pref": "Male",
        "amenities": [
            "WiFi",
            "Geyser",
            "Food Included"
        ],
        "description": "PG for working professionals. Food and laundry included.",
        "photo_url": None,
        "posted_by": "user_hash_vwx",
        "date_posted": "2025-08-03",
        "is_active": True,
        "expires_at": "2025-09-02",
        "spots_available": 2
    },
    {
        "id": "R008",
        "location": {
            "city": "Mumbai",
            "area": "Andheri East",
            "pincode": "400099"
        },
        "rent": 25000,
        "gender_pref": "Any",
        "amenities": [
            "WiFi",
            "AC",
            "Washing Machine",
            "Gym",
            "Swimming Pool"
        ],
        "description": "Studio apartment in a modern complex with all facilities.",
        "photo_url": "https://example.com/img8.jpg",
        "posted_by": "user_hash_yza",
        "date_posted": "2025-08-04",
        "is_active": True,
        "expires_at": "2025-09-03",
        "spots_available": 1
    },
    {
        "id": "R009",
        "location": {
            "city": "Bengaluru",
            "area": "Jayanagar",
            "pincode": "560041"
        },
        "rent": 14000,
        "gender_pref": "Female",
        "amenities": [
            "WiFi",
            "Balcony",
            "Parking"
        ],
        "description": "Peaceful room in a quiet residential area. Gated society.",
        "photo_url": None,
        "posted_by": "user_hash_bcd",
        "date_posted": "2025-08-06",
        "is_active": True,
        "expires_at": "2025-09-05",
        "spots_available": 1
    },
    {
        "id": "R010",
        "location": {
            "city": "Pune",
            "area": "Koregaon Park",
            "pincode": "411001"
        },
        "rent": 17000,
        "gender_pref": "Any",
        "amenities": [
            "WiFi",
            "AC",
            "Washing Machine"
        ],
        "description": "Stylish 1BHK with a large balcony. Centrally located.",
        "photo_url": "https://example.com/img10.jpg",
        "posted_by": "user_hash_cde",
        "date_posted": "2025-08-07",
        "is_active": True,
        "expires_at": "2025-09-06",
        "spots_available": 1
    },
    {
        "id": "R011",
        "location": {
            "city": "Hyderabad",
            "area": "Gachibowli",
            "pincode": "500032"
        },
        "rent": 11000,
        "gender_pref": "Male",
        "amenities": [
            "WiFi",
            "AC",
            "Food Included"
        ],
        "description": "Shared room in a high-end PG. All meals provided.",
        "photo_url": "https://example.com/img11.jpg",
        "posted_by": "user_hash_efg",
        "date_posted": "2025-08-08",
        "is_active": True,
        "expires_at": "2025-09-07",
        "spots_available": 2
    },
    {
        "id": "R012",
        "location": {
            "city": "Chennai",
            "area": "Adyar",
            "pincode": "600020"
        },
        "rent": 13500,
        "gender_pref": "Female",
        "amenities": [
            "WiFi",
            "Geyser",
            "Security"
        ],
        "description": "Independent room in a peaceful and secure neighborhood.",
        "photo_url": None,
        "posted_by": "user_hash_fgh",
        "date_posted": "2025-08-09",
        "is_active": True,
        "expires_at": "2025-09-08",
        "spots_available": 1
    },
    {
        "id": "R013",
        "location": {
            "city": "Bengaluru",
            "area": "Whitefield",
            "pincode": "560066"
        },
        "rent": 11500,
        "gender_pref": "Any",
        "amenities": [
            "WiFi",
            "AC",
            "Washing Machine"
        ],
        "description": "Semi-furnished room in a 3BHK near ITPL.",
        "photo_url": "https://example.com/img13.jpg",
        "posted_by": "user_hash_ghi",
        "date_posted": "2025-08-10",
        "is_active": True,
        "expires_at": "2025-09-09",
        "spots_available": 1
    },
    {
        "id": "R014",
        "location": {
            "city": "Pune",
            "area": "Baner",
            "pincode": "411045"
        },
        "rent": 16500,
        "gender_pref": "Male",
        "amenities": [
            "WiFi",
            "AC",
            "Parking",
            "Gym"
        ],
        "description": "Room in a premium apartment with great amenities.",
        "photo_url": "https://example.com/img14.jpg",
        "posted_by": "user_hash_hij",
        "date_posted": "2025-08-11",
        "is_active": True,
        "expires_at": "2025-09-10",
        "spots_available": 1
    }
]
