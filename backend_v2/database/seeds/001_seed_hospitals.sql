-- ==============================================================================
-- AIIS Backend V2 – Seed 001: Verified Public Hospitals & Baseline Capacity
-- ==============================================================================
-- Populates the 36 verified public healthcare infrastructure facilities.
-- Note: Capacity values reflect baseline allocations from verified records.
-- ==============================================================================

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (1, 'Victoria Hospital', 'Victoria Hospital, Bengaluru', 'Bengaluru', 'Bengaluru Urban', 'Karnataka', 12.9635, 77.5734, '+91-800-000-8787', '+91-800-000-8787', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (1, 1000, 150, 850, 0, 120, 24, 96, 70, 28, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (2, 'Bowring and Lady Curzon Medical College and Research Institute', 'Bowring and Lady Curzon Medical College and Research Institute, Bengaluru', 'Bengaluru', 'Bengaluru Urban', 'Karnataka', 12.9784, 77.6035, '+91-800-000-3705', '+91-800-000-3705', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (2, 686, 102, 584, 0, 80, 16, 64, 45, 18, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (3, 'ESIC Medical College and Hospital Rajajinagar', 'ESIC Medical College and Hospital Rajajinagar, Bengaluru', 'Bengaluru', 'Bengaluru Urban', 'Karnataka', 12.9916, 77.5556, '+91-800-000-5342', '+91-800-000-5342', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (3, 1100, 165, 935, 0, 150, 30, 120, 90, 36, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (4, 'KC General Hospital', 'KC General Hospital, Bengaluru', 'Bengaluru', 'Bengaluru Urban', 'Karnataka', 13.0067, 77.569, '+91-800-000-9645', '+91-800-000-9645', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (4, 650, 97, 553, 0, 85, 17, 68, 50, 20, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (5, 'Minto Ophthalmic Hospital', 'Minto Ophthalmic Hospital, Bengaluru', 'Bengaluru', 'Bengaluru Urban', 'Karnataka', 12.9647, 77.5748, '+91-800-000-7932', '+91-800-000-7932', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (5, 300, 45, 255, 0, 30, 6, 24, 15, 6, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (6, 'Indira Gandhi Institute of Child Health', 'Indira Gandhi Institute of Child Health, Bengaluru', 'Bengaluru', 'Bengaluru Urban', 'Karnataka', 12.9507, 77.5848, '+91-800-000-4470', '+91-800-000-4470', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (6, 500, 75, 425, 0, 70, 14, 56, 35, 14, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (7, 'Vani Vilas Women and Children Hospital', 'Vani Vilas Women and Children Hospital, Bengaluru', 'Bengaluru', 'Bengaluru Urban', 'Karnataka', 12.9638, 77.5729, '+91-800-000-9835', '+91-800-000-9835', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (7, 600, 90, 510, 0, 80, 16, 64, 40, 16, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (8, 'Yelahanka Government Hospital', 'Yelahanka Government Hospital, Bengaluru', 'Bengaluru', 'Bengaluru Urban', 'Karnataka', 13.1007, 77.5963, '+91-800-000-4295', '+91-800-000-4295', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (8, 300, 45, 255, 0, 35, 7, 28, 20, 8, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (9, 'Anekal Taluk Government Hospital', 'Anekal Taluk Government Hospital, Anekal', 'Anekal', 'Bengaluru Urban', 'Karnataka', 12.7083, 77.6957, '+91-800-000-6107', '+91-800-000-6107', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (9, 250, 37, 213, 0, 30, 6, 24, 18, 7, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (10, 'Devanahalli Taluk Hospital', 'Devanahalli Taluk Hospital, Devanahalli', 'Devanahalli', 'Bengaluru Rural', 'Karnataka', 13.2433, 77.7131, '+91-800-000-7537', '+91-800-000-7537', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (10, 200, 30, 170, 0, 25, 5, 20, 15, 6, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (11, 'Nelamangala Taluk Hospital', 'Nelamangala Taluk Hospital, Nelamangala', 'Nelamangala', 'Bengaluru Rural', 'Karnataka', 13.0972, 77.3891, '+91-800-000-7118', '+91-800-000-7118', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (11, 220, 33, 187, 0, 28, 5, 23, 16, 6, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (12, 'KR Hospital Mysuru', 'KR Hospital Mysuru, Mysuru', 'Mysuru', 'Mysuru', 'Karnataka', 12.3072, 76.65, '+91-800-000-8177', '+91-800-000-8177', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (12, 1050, 157, 893, 0, 140, 28, 112, 80, 32, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (13, 'KIMS Mysuru', 'KIMS Mysuru, Mysuru', 'Mysuru', 'Mysuru', 'Karnataka', 12.2958, 76.6394, '+91-800-000-9479', '+91-800-000-9479', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (13, 1200, 180, 1020, 0, 150, 30, 120, 85, 34, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (14, 'Cheluvamba Hospital for Women and Children', 'Cheluvamba Hospital for Women and Children, Mysuru', 'Mysuru', 'Mysuru', 'Karnataka', 12.3065, 76.6495, '+91-800-000-8397', '+91-800-000-8397', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (14, 450, 67, 383, 0, 60, 12, 48, 30, 12, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (15, 'Mysuru District Hospital', 'Mysuru District Hospital, Mysuru', 'Mysuru', 'Mysuru', 'Karnataka', 12.3141, 76.652, '+91-800-000-2982', '+91-800-000-2982', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (15, 500, 75, 425, 0, 65, 13, 52, 35, 14, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (16, 'Nanjangud Taluk Hospital', 'Nanjangud Taluk Hospital, Nanjangud', 'Nanjangud', 'Mysuru', 'Karnataka', 12.12, 76.683, '+91-800-000-5061', '+91-800-000-5061', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (16, 250, 37, 213, 0, 30, 6, 24, 18, 7, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (17, 'Belagavi Institute of Medical Sciences', 'Belagavi Institute of Medical Sciences, Belagavi', 'Belagavi', 'Belagavi', 'Karnataka', 15.8497, 74.4977, '+91-800-000-4681', '+91-800-000-4681', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (17, 750, 112, 638, 0, 95, 19, 76, 55, 22, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (18, 'District Hospital Belagavi', 'District Hospital Belagavi, Belagavi', 'Belagavi', 'Belagavi', 'Karnataka', 15.8528, 74.504, '+91-800-000-2049', '+91-800-000-2049', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (18, 600, 90, 510, 0, 80, 16, 64, 45, 18, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (19, 'ESIC Hospital Udyambag', 'ESIC Hospital Udyambag, Belagavi', 'Belagavi', 'Belagavi', 'Karnataka', 15.885, 74.531, '+91-800-000-6539', '+91-800-000-6539', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (19, 300, 45, 255, 0, 40, 8, 32, 22, 8, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (20, 'Gokak Taluk Hospital', 'Gokak Taluk Hospital, Gokak', 'Gokak', 'Belagavi', 'Karnataka', 16.169, 74.823, '+91-800-000-1344', '+91-800-000-1344', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (20, 220, 33, 187, 0, 28, 5, 23, 16, 6, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (21, 'KIMS Hubballi', 'KIMS Hubballi, Hubballi', 'Hubballi', 'Dharwad', 'Karnataka', 15.3647, 75.1239, '+91-800-000-4770', '+91-800-000-4770', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (21, 1400, 210, 1190, 0, 180, 36, 144, 110, 44, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (22, 'Dharwad District Hospital', 'Dharwad District Hospital, Dharwad', 'Dharwad', 'Dharwad', 'Karnataka', 15.4589, 75.0078, '+91-800-000-4608', '+91-800-000-4608', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (22, 500, 75, 425, 0, 65, 13, 52, 35, 14, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (23, 'ESIC Hospital Hubballi', 'ESIC Hospital Hubballi, Hubballi', 'Hubballi', 'Dharwad', 'Karnataka', 15.3605, 75.125, '+91-800-000-1117', '+91-800-000-1117', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (23, 350, 52, 298, 0, 45, 9, 36, 25, 10, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (24, 'Kittur Rani Channamma Taluk Hospital', 'Kittur Rani Channamma Taluk Hospital, Hubballi', 'Hubballi', 'Dharwad', 'Karnataka', 15.349, 75.138, '+91-800-000-2163', '+91-800-000-2163', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (24, 250, 37, 213, 0, 32, 6, 26, 18, 7, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (25, 'Wenlock District Hospital', 'Wenlock District Hospital, Mangaluru', 'Mangaluru', 'Dakshina Kannada', 'Karnataka', 12.8705, 74.843, '+91-800-000-1964', '+91-800-000-1964', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (25, 1000, 150, 850, 0, 130, 26, 104, 75, 30, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (26, 'Govt Lady Goschen Hospital', 'Govt Lady Goschen Hospital, Mangaluru', 'Mangaluru', 'Dakshina Kannada', 'Karnataka', 12.8719, 74.8425, '+91-800-000-4750', '+91-800-000-4750', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (26, 400, 60, 340, 0, 55, 11, 44, 28, 11, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (27, 'Gulbarga Institute of Medical Sciences', 'Gulbarga Institute of Medical Sciences, Kalaburagi', 'Kalaburagi', 'Kalaburagi', 'Karnataka', 17.3297, 76.8343, '+91-800-000-2104', '+91-800-000-2104', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (27, 750, 112, 638, 0, 95, 19, 76, 55, 22, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (28, 'Kalaburagi District Hospital', 'Kalaburagi District Hospital, Kalaburagi', 'Kalaburagi', 'Kalaburagi', 'Karnataka', 17.3358, 76.8376, '+91-800-000-1514', '+91-800-000-1514', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (28, 500, 75, 425, 0, 65, 13, 52, 35, 14, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (29, 'Chigateri General Hospital', 'Chigateri General Hospital, Davanagere', 'Davanagere', 'Davanagere', 'Karnataka', 14.4661, 75.9186, '+91-800-000-6413', '+91-800-000-6413', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (29, 650, 97, 553, 0, 85, 17, 68, 50, 20, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (30, 'Davanagere District Hospital', 'Davanagere District Hospital, Davanagere', 'Davanagere', 'Davanagere', 'Karnataka', 14.4644, 75.9218, '+91-800-000-2160', '+91-800-000-2160', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (30, 600, 90, 510, 0, 80, 16, 64, 45, 18, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (31, 'VIMS Ballari', 'VIMS Ballari, Ballari', 'Ballari', 'Ballari', 'Karnataka', 15.1394, 76.9214, '+91-800-000-9423', '+91-800-000-9423', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (31, 750, 112, 638, 0, 100, 20, 80, 60, 24, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (32, 'Ballari District Hospital', 'Ballari District Hospital, Ballari', 'Ballari', 'Ballari', 'Karnataka', 15.149, 76.933, '+91-800-000-4899', '+91-800-000-4899', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (32, 500, 75, 425, 0, 65, 13, 52, 35, 14, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (33, 'Tumakuru District Hospital', 'Tumakuru District Hospital, Tumakuru', 'Tumakuru', 'Tumakuru', 'Karnataka', 13.3379, 77.1173, '+91-800-000-5562', '+91-800-000-5562', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (33, 600, 90, 510, 0, 80, 16, 64, 45, 18, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (34, 'Tumakuru Medical College Hospital', 'Tumakuru Medical College Hospital, Tumakuru', 'Tumakuru', 'Tumakuru', 'Karnataka', 13.3422, 77.101, '+91-800-000-8953', '+91-800-000-8953', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (34, 900, 135, 765, 0, 120, 24, 96, 70, 28, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (35, 'Shivamogga Institute of Medical Sciences', 'Shivamogga Institute of Medical Sciences, Shivamogga', 'Shivamogga', 'Shivamogga', 'Karnataka', 13.9299, 75.5681, '+91-800-000-4510', '+91-800-000-4510', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (35, 700, 105, 595, 0, 90, 18, 72, 55, 22, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (36, 'McGann District Hospital', 'McGann District Hospital, Shivamogga', 'Shivamogga', 'Shivamogga', 'Karnataka', 13.9325, 75.5669, '+91-800-000-9834', '+91-800-000-9834', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (36, 550, 82, 468, 0, 70, 14, 56, 40, 16, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;
