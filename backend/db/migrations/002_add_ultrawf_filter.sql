-- Update existing ULTRAWF filter with description, image, ASIN, and purchase URL
UPDATE consumables
SET description = 'Frigidaire ULTRAWF PureSource Ultra replacement refrigerator water filter. Compatible with Frigidaire and Kenmore models. Reduces contaminants including chlorine, lead, and mercury for cleaner, better-tasting water.',
    image_url = 'https://m.media-amazon.com/images/I/61XUX7JzKeL._AC_SL1500_.jpg',
    asin = COALESCE(asin, 'B0GGH4YFYV'),
    purchase_url = 'https://www.amazon.com/dp/B0GGH4YFYV?tag=be3857-20'
WHERE sku = 'ULTRAWF';
