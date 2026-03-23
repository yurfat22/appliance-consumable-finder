-- Update existing EDR1RXD1 filter with description, image, ASIN, and purchase URL
UPDATE consumables
SET description = 'Glacier Fresh replacement refrigerator water filter compatible with EveryDrop EDR1RXD1, Whirlpool W10295370A, and W10295370. Reduces chlorine, lead, and contaminants for cleaner water. Easy twist-in installation.',
    image_url = 'https://m.media-amazon.com/images/I/51MwB5hl-kL._AC_SL1500_.jpg',
    asin = COALESCE(asin, 'B0CPDZ4Y2P'),
    purchase_url = 'https://www.amazon.com/dp/B0CPDZ4Y2P?tag=be3857-20'
WHERE sku = 'EDR1RXD1';
