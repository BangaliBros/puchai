from typing import List, Dict, Any

ROOMS_DB: List[Dict[str, Any]] = [
    {
        "id": "R005",
        "management_key": "test-key-for-r005", # Changed from posted_by
        "location": {"city": "Bengaluru", "area": "Marathahalli", "pincode": "560037"},
        "rent": 10500, "gender_pref": "Any", "amenities": ["WiFi", "Geyser"],
        "description": "Spacious single room in a 2BHK apartment. Close to IT parks.",
        "photo_url": "https://example.com/img5.jpg",
        "date_posted": "2025-08-01", "is_active": True, "expires_at": "2025-08-31",
        "spots_available": 1
    },
    {
        "id": "R006",
        "management_key": "test-key-for-r006", # Changed from posted_by
        "location": {"city": "Bengaluru", "area": "Indiranagar", "pincode": "560038"},
        "rent": 18000, "gender_pref": "Female", "amenities": ["WiFi", "AC", "Washing Machine", "Balcony"],
        "description": "Luxurious 1BHK near the metro station. Fully furnished.",
        "photo_url": "https://example.com/img6.jpg",
        "date_posted": "2025-08-02", "is_active": True, "expires_at": "2025-09-01",
        "spots_available": 1
    },
    # ... Update all other entries similarly ...
]