-- Update existing EDR4RXD1 filter with description, image, ASIN, and purchase URL
UPDATE consumables
SET description = 'Waterdrop replacement refrigerator water filter compatible with EveryDrop EDR4RXD1, Whirlpool UKF8001, UKF8001AXX, and Maytag. Reduces chlorine, lead, mercury, and other contaminants. Quick twist-and-lock installation.',
    image_url = 'https://m.media-amazon.com/images/I/61bgWO8WTJL._AC_SL1500_.jpg',
    asin = COALESCE(asin, 'B079S5N27S'),
    purchase_url = 'https://www.amazon.com/dp/B079S5N27S?tag=be3857-20'
WHERE sku = 'EDR4RXD1';
