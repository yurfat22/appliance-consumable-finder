-- Update existing RPWFE filter with description, image, ASIN, and purchase URL
UPDATE consumables
SET description = 'GE RPWFE refrigerator water filter. Genuine GE replacement with RFID chip for compatible models. Certified to reduce lead, mercury, cadmium, and 50+ other contaminants. Twist-and-lock installation.',
    image_url = 'https://m.media-amazon.com/images/I/71dfZ714jtL._AC_SL1500_.jpg',
    asin = COALESCE(asin, 'B009PCI2JU'),
    purchase_url = 'https://www.amazon.com/dp/B009PCI2JU?tag=be3857-20'
WHERE sku = 'RPWFE';
