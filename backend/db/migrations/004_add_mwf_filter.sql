-- Update existing MWF filter with description, image, ASIN, and purchase URL
UPDATE consumables
SET description = 'Glacier Fresh replacement refrigerator water filter compatible with GE MWF, MWFP, MWFA, GWF, GWFA, and Kenmore 46-9991. Reduces chlorine, sediment, and other contaminants for cleaner drinking water.',
    image_url = 'https://m.media-amazon.com/images/I/51T4p83o4oL._AC_SL1500_.jpg',
    asin = COALESCE(asin, 'B07D4JT2ZJ'),
    purchase_url = 'https://www.amazon.com/dp/B07D4JT2ZJ?tag=be3857-20'
WHERE sku = 'MWF';
