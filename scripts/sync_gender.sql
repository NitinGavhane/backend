-- Run directly on Neon DB to fix category & product genders
-- MEN tab → Men, Footwear, Kurtas, Shirts
-- WOMEN tab → Women
-- KIDS tab → Kids

ALTER TABLE categories ADD COLUMN IF NOT EXISTS gender VARCHAR(20) NOT NULL DEFAULT 'unisex';

UPDATE categories SET gender = 'men'   WHERE LOWER(TRIM(name)) IN ('men', 'footwear', 'kurtas', 'shirts');
UPDATE categories SET gender = 'women' WHERE LOWER(TRIM(name)) = 'women';
UPDATE categories SET gender = 'kids'  WHERE LOWER(TRIM(name)) = 'kids';

ALTER TABLE products ADD COLUMN IF NOT EXISTS gender VARCHAR(20) NOT NULL DEFAULT 'unisex';

UPDATE products p
SET gender = c.gender
FROM categories c
WHERE p.category_id = c.id;
