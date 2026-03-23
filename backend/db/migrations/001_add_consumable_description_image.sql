-- Add description and image_url columns to consumables
ALTER TABLE consumables ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE consumables ADD COLUMN IF NOT EXISTS image_url TEXT;

-- Update existing BORPLFTR50 filter with description, image, ASIN, and purchase URL
UPDATE consumables
SET description = 'ICEPURE replacement refrigerator water filter compatible with Bosch BORPLFTR50, BORPLFTR55, and UltraClarity Pro. NSF 42 certified to reduce chlorine, taste, and odor. Easy twist-and-lock installation.',
    image_url = 'https://m.media-amazon.com/images/I/61H-QY1YRiL._AC_SL1500_.jpg',
    asin = 'B0CC1GTSSS',
    purchase_url = 'https://www.amazon.com/dp/B0CC1GTSSS?tag=be3857-20'
WHERE sku = 'BORPLFTR50';
