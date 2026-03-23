-- Update existing EPTWFU01 filter with description, image, ASIN, and purchase URL
UPDATE consumables
SET description = 'Replacement refrigerator water filter compatible with Frigidaire EPTWFU01, PureSource Ultra II. Reduces chlorine, lead, and other contaminants for cleaner, better-tasting water. Easy push-in installation.',
    image_url = 'https://m.media-amazon.com/images/I/71wimnik76L._AC_SL1500_.jpg',
    asin = COALESCE(asin, 'B0B2RPVWNR'),
    purchase_url = 'https://www.amazon.com/dp/B0B2RPVWNR?tag=be3857-20'
WHERE sku = 'EPTWFU01';
