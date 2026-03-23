-- Update existing MSWF filter with description, image, ASIN, and purchase URL
UPDATE consumables
SET description = 'GE MSWF refrigerator water filter. Genuine GE replacement for side-by-side and bottom-freezer models. Reduces chlorine, lead, mercury, and other contaminants. Simple slide-in installation.',
    image_url = 'https://m.media-amazon.com/images/I/81WOMr2qFaL._AC_SL1500_.jpg',
    asin = COALESCE(asin, 'B00126NABC'),
    purchase_url = 'https://www.amazon.com/dp/B00126NABC?tag=be3857-20'
WHERE sku = 'MSWF';
