-- Update existing XWFE filter with description, image, ASIN, and purchase URL
UPDATE consumables
SET description = 'GE Appliances XWFE refrigerator water filter. Genuine GE replacement with chip for compatible models. Reduces lead, trace pharmaceuticals, and 50+ other contaminants. Easy twist-in installation.',
    image_url = 'https://m.media-amazon.com/images/I/71Z4DYovOvL._AC_SL1500_.jpg',
    asin = COALESCE(asin, 'B0882ZJ48W'),
    purchase_url = 'https://www.amazon.com/dp/B0882ZJ48W?tag=be3857-20'
WHERE sku = 'XWFE';
