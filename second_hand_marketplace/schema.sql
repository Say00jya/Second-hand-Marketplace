-- =====================================================================
--  ReMarket : Second-Hand Marketplace
--  Database : second_hand_marketplace   (MySQL 8.x / MariaDB 10.5+)
--  Run with : mysql -u root -p < schema.sql
--  WARNING  : re-running this file drops and recreates all tables.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS second_hand_marketplace
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE second_hand_marketplace;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS reports;
DROP TABLE IF EXISTS inquiries;
DROP TABLE IF EXISTS wishlist;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS users;
SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------
-- 1. USERS
-- ---------------------------------------------------------------------
CREATE TABLE users (
    user_id        INT AUTO_INCREMENT PRIMARY KEY,
    full_name      VARCHAR(100) NOT NULL,
    email          VARCHAR(120) NOT NULL UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,
    phone          VARCHAR(15)  NOT NULL,
    location       VARCHAR(100) NOT NULL,
    role           ENUM('user','admin') NOT NULL DEFAULT 'user',
    is_active      TINYINT(1)   NOT NULL DEFAULT 1,
    created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_users_phone CHECK (CHAR_LENGTH(phone) BETWEEN 10 AND 15),
    CONSTRAINT chk_users_email CHECK (email LIKE '%_@_%._%'),
    CONSTRAINT chk_users_active CHECK (is_active IN (0, 1))
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 2. CATEGORIES
-- ---------------------------------------------------------------------
CREATE TABLE categories (
    category_id  INT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(50)  NOT NULL UNIQUE,
    description  VARCHAR(255) NULL,
    icon         VARCHAR(40)  NOT NULL DEFAULT 'bi-grid',
    created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 3. PRODUCTS   (many products -> one seller, many products -> one category)
-- ---------------------------------------------------------------------
CREATE TABLE products (
    product_id      INT AUTO_INCREMENT PRIMARY KEY,
    seller_id       INT NOT NULL,
    category_id     INT NOT NULL,
    title           VARCHAR(150)  NOT NULL,
    description     TEXT          NOT NULL,
    price           DECIMAL(10,2) NOT NULL,
    item_condition  ENUM('New','Like New','Good','Fair') NOT NULL DEFAULT 'Good',
    location        VARCHAR(100)  NOT NULL,
    image           VARCHAR(255)  NOT NULL DEFAULT 'placeholder-other.svg',
    status          ENUM('active','sold','removed') NOT NULL DEFAULT 'active',
    is_featured     TINYINT(1)    NOT NULL DEFAULT 0,
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT chk_products_price CHECK (price > 0),
    CONSTRAINT fk_products_seller   FOREIGN KEY (seller_id)   REFERENCES users(user_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_products_category FOREIGN KEY (category_id) REFERENCES categories(category_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX idx_products_status_created (status, created_at),
    INDEX idx_products_category (category_id),
    INDEX idx_products_price (price),
    INDEX idx_products_location (location)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 4. WISHLIST   (many-to-many between users and products)
-- ---------------------------------------------------------------------
CREATE TABLE wishlist (
    wishlist_id  INT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT NOT NULL,
    product_id   INT NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_wishlist_user_product UNIQUE (user_id, product_id),
    CONSTRAINT fk_wishlist_user    FOREIGN KEY (user_id)    REFERENCES users(user_id)       ON DELETE CASCADE,
    CONSTRAINT fk_wishlist_product FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 5. INQUIRIES  (a buyer sends a message about a product; the seller is
--                found through products.seller_id)
-- ---------------------------------------------------------------------
CREATE TABLE inquiries (
    inquiry_id  INT AUTO_INCREMENT PRIMARY KEY,
    product_id  INT NOT NULL,
    sender_id   INT NOT NULL,
    message     VARCHAR(1000) NOT NULL,
    is_read     TINYINT(1) NOT NULL DEFAULT 0,
    created_at  TIMESTAMP  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_inquiries_message CHECK (CHAR_LENGTH(message) >= 10),
    CONSTRAINT fk_inquiries_product FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE,
    CONSTRAINT fk_inquiries_sender  FOREIGN KEY (sender_id)  REFERENCES users(user_id)       ON DELETE CASCADE,
    INDEX idx_inquiries_product (product_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 6. REPORTS    (a user reports a listing; admin resolves it)
-- ---------------------------------------------------------------------
CREATE TABLE reports (
    report_id    INT AUTO_INCREMENT PRIMARY KEY,
    product_id   INT NOT NULL,
    reporter_id  INT NOT NULL,
    reason       VARCHAR(100) NOT NULL,
    details      VARCHAR(500) NULL,
    status       ENUM('pending','resolved','dismissed') NOT NULL DEFAULT 'pending',
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at  TIMESTAMP NULL DEFAULT NULL,
    CONSTRAINT fk_reports_product  FOREIGN KEY (product_id)  REFERENCES products(product_id) ON DELETE CASCADE,
    CONSTRAINT fk_reports_reporter FOREIGN KEY (reporter_id) REFERENCES users(user_id)       ON DELETE CASCADE,
    INDEX idx_reports_status (status)
) ENGINE=InnoDB;

-- =====================================================================
--  SAMPLE DATA  (all names, numbers and e-mails are fictional)
--  Passwords:  admin -> Admin@123      every other user -> User@123
-- =====================================================================

INSERT INTO users (user_id, full_name, email, password_hash, phone, location, role, is_active, created_at) VALUES
(1,  'ReMarket Admin',   'admin@remarket.in',  'scrypt:32768:8:1$c6mOtWetVWFWEqSJ$98db4660a3d11c02147b2299ff68897e19d33b89417701e2cda8d4da3c07dd681ed3b0c3cbb036e093173d080dd387e6b2e29e304d30265149572f4ec8ca3f15', '9400000001', 'Kochi',              'admin', 1, DATE_SUB(NOW(), INTERVAL 120 DAY)),
(2,  'Anu Mathew',       'anu@example.com',    'scrypt:32768:8:1$7JBUx0jHTCn0CuW5$da378c66153bcfeb0a7fd1a1fd5e5bd36fdc25401038dcb2171cc864d1da76979aa90456727b2fc75f34280378a41bc6618fd1140efd556bb7c159932d410a98',  '9400000002', 'Kochi',              'user',  1, DATE_SUB(NOW(), INTERVAL 90 DAY)),
(3,  'Rahul Nair',       'rahul@example.com',  'scrypt:32768:8:1$7JBUx0jHTCn0CuW5$da378c66153bcfeb0a7fd1a1fd5e5bd36fdc25401038dcb2171cc864d1da76979aa90456727b2fc75f34280378a41bc6618fd1140efd556bb7c159932d410a98',  '9400000003', 'Kottayam',           'user',  1, DATE_SUB(NOW(), INTERVAL 80 DAY)),
(4,  'Fathima Beevi',    'fathima@example.com','scrypt:32768:8:1$7JBUx0jHTCn0CuW5$da378c66153bcfeb0a7fd1a1fd5e5bd36fdc25401038dcb2171cc864d1da76979aa90456727b2fc75f34280378a41bc6618fd1140efd556bb7c159932d410a98',  '9400000004', 'Kozhikode',          'user',  1, DATE_SUB(NOW(), INTERVAL 70 DAY)),
(5,  'Joseph Kurian',    'joseph@example.com', 'scrypt:32768:8:1$7JBUx0jHTCn0CuW5$da378c66153bcfeb0a7fd1a1fd5e5bd36fdc25401038dcb2171cc864d1da76979aa90456727b2fc75f34280378a41bc6618fd1140efd556bb7c159932d410a98',  '9400000005', 'Pathanamthitta',     'user',  1, DATE_SUB(NOW(), INTERVAL 60 DAY)),
(6,  'Sneha Menon',      'sneha@example.com',  'scrypt:32768:8:1$7JBUx0jHTCn0CuW5$da378c66153bcfeb0a7fd1a1fd5e5bd36fdc25401038dcb2171cc864d1da76979aa90456727b2fc75f34280378a41bc6618fd1140efd556bb7c159932d410a98',  '9400000006', 'Thiruvananthapuram', 'user',  1, DATE_SUB(NOW(), INTERVAL 50 DAY)),
(7,  'Arjun Pillai',     'arjun@example.com',  'scrypt:32768:8:1$7JBUx0jHTCn0CuW5$da378c66153bcfeb0a7fd1a1fd5e5bd36fdc25401038dcb2171cc864d1da76979aa90456727b2fc75f34280378a41bc6618fd1140efd556bb7c159932d410a98',  '9400000007', 'Ernakulam',          'user',  1, DATE_SUB(NOW(), INTERVAL 40 DAY)),
(8,  'Meera Krishnan',   'meera@example.com',  'scrypt:32768:8:1$7JBUx0jHTCn0CuW5$da378c66153bcfeb0a7fd1a1fd5e5bd36fdc25401038dcb2171cc864d1da76979aa90456727b2fc75f34280378a41bc6618fd1140efd556bb7c159932d410a98',  '9400000008', 'Kochi',              'user',  1, DATE_SUB(NOW(), INTERVAL 30 DAY)),
(9,  'Vishnu Prasad',    'vishnu@example.com', 'scrypt:32768:8:1$7JBUx0jHTCn0CuW5$da378c66153bcfeb0a7fd1a1fd5e5bd36fdc25401038dcb2171cc864d1da76979aa90456727b2fc75f34280378a41bc6618fd1140efd556bb7c159932d410a98',  '9400000009', 'Kottayam',           'user',  1, DATE_SUB(NOW(), INTERVAL 20 DAY)),
(10, 'Nisha Thomas',     'nisha@example.com',  'scrypt:32768:8:1$7JBUx0jHTCn0CuW5$da378c66153bcfeb0a7fd1a1fd5e5bd36fdc25401038dcb2171cc864d1da76979aa90456727b2fc75f34280378a41bc6618fd1140efd556bb7c159932d410a98',  '9400000010', 'Kozhikode',          'user',  1, DATE_SUB(NOW(), INTERVAL 10 DAY)),
(11, 'Divya Raj',        'divya@example.com',  'scrypt:32768:8:1$7JBUx0jHTCn0CuW5$da378c66153bcfeb0a7fd1a1fd5e5bd36fdc25401038dcb2171cc864d1da76979aa90456727b2fc75f34280378a41bc6618fd1140efd556bb7c159932d410a98', '9400000011', 'Kochi',              'user',  1, DATE_SUB(NOW(), INTERVAL 5 DAY));

INSERT INTO categories (category_id, name, description, icon) VALUES
(1,  'Electronics',      'TVs, audio, cameras and gadgets',            'bi-tv'),
(2,  'Mobiles',          'Smartphones, tablets and accessories',       'bi-phone'),
(3,  'Laptops',          'Laptops, desktops and computer parts',       'bi-laptop'),
(4,  'Furniture',        'Sofas, tables, beds and storage',            'bi-lamp'),
(5,  'Books',            'Textbooks, exam guides and novels',          'bi-book'),
(6,  'Fashion',          'Clothing, footwear and accessories',         'bi-bag'),
(7,  'Vehicles',         'Bikes, scooters, cars and cycles',           'bi-car-front'),
(8,  'Home Appliances',  'Washing machines, cookers and kitchenware',  'bi-plug'),
(9,  'Sports',           'Sports gear, fitness and outdoor items',     'bi-trophy'),
(10, 'Other',            'Everything else that deserves a new home',   'bi-grid');

INSERT INTO products (product_id, seller_id, category_id, title, description, price, item_condition, location, image, status, is_featured, created_at) VALUES
(1,  2, 2,  'iPhone 12 128GB (Blue)', 'Used for two years with a screen guard and case from day one. Battery health is 86 percent. Comes with the original box and a fast charger. No scratches on the display.', 28500.00, 'Good', 'Kochi', 'placeholder-mobiles.svg', 'active', 1, DATE_SUB(NOW(), INTERVAL 2 DAY)),
(2,  3, 2,  'Samsung Galaxy M31 6GB/128GB', 'Reliable phone with a big battery. Small dent on the frame, screen is clean. Charger included, bill not available.', 9500.00, 'Fair', 'Kottayam', 'placeholder-mobiles.svg', 'active', 0, DATE_SUB(NOW(), INTERVAL 6 DAY)),
(3,  7, 2,  'Redmi Note 10 Pro 6GB', 'Selling because I upgraded. Works perfectly, AMOLED display, 33W charger in the box. Two months of warranty left.', 11000.00, 'Good', 'Ernakulam', 'placeholder-mobiles.svg', 'active', 0, DATE_SUB(NOW(), INTERVAL 9 DAY)),
(4,  4, 3,  'Dell Inspiron 15 (i5, 8GB, 512GB SSD)', 'Ideal laptop for students. 10th gen Core i5, 8GB RAM, 512GB SSD, Windows 11 licensed. Battery gives about 4 hours. Bag included.', 24500.00, 'Good', 'Kozhikode', 'placeholder-laptops.svg', 'active', 1, DATE_SUB(NOW(), INTERVAL 3 DAY)),
(5,  6, 3,  'HP Pavilion 14 Ryzen 5', 'Bought last year, hardly used. Lightweight laptop with a backlit keyboard, 16GB RAM upgrade done by the service centre. Bill and warranty card available.', 31000.00, 'Like New', 'Thiruvananthapuram', 'placeholder-laptops.svg', 'active', 0, DATE_SUB(NOW(), INTERVAL 12 DAY)),
(6,  8, 3,  'Lenovo ThinkPad T480', 'Sturdy business laptop, i5 8th gen with 16GB RAM. Keyboard is excellent. Minor wear on the palm rest.', 19500.00, 'Fair', 'Kochi', 'placeholder-laptops.svg', 'active', 0, DATE_SUB(NOW(), INTERVAL 15 DAY)),
(7,  5, 4,  'Teak Wood 3-Seater Sofa', 'Solid teak frame with cushions re-done last year. Moving to a smaller flat so we have to sell. Pickup only from Pathanamthitta town.', 18000.00, 'Good', 'Pathanamthitta', 'placeholder-furniture.svg', 'active', 1, DATE_SUB(NOW(), INTERVAL 4 DAY)),
(8,  9, 4,  'Study Table with 3 Drawers', 'Engineered wood study table with a lockable drawer and a shelf. Sturdy, no wobble. Can help with loading.', 3500.00, 'Good', 'Kottayam', 'placeholder-furniture.svg', 'active', 0, DATE_SUB(NOW(), INTERVAL 18 DAY)),
(9,  2, 5,  'B.Tech Engineering Mathematics Books (S1 and S2)', 'Complete set of KTU first-year mathematics and physics textbooks with solved problem notes. Very little highlighting.', 650.00, 'Good', 'Kochi', 'placeholder-books.svg', 'active', 0, DATE_SUB(NOW(), INTERVAL 5 DAY)),
(10, 10, 5, 'Kerala PSC Preparation Book Bundle', 'Ten guide books and last five years of question papers for Kerala PSC exams. Latest edition from 2023.', 800.00, 'Fair', 'Kozhikode', 'placeholder-books.svg', 'active', 0, DATE_SUB(NOW(), INTERVAL 21 DAY)),
(11, 7, 6,  'Men''s Leather Jacket (Size L)', 'Genuine leather jacket worn only a handful of times. Perfect for bike rides. Dry cleaned and ready to use.', 2200.00, 'Like New', 'Ernakulam', 'placeholder-fashion.svg', 'active', 0, DATE_SUB(NOW(), INTERVAL 7 DAY)),
(12, 6, 6,  'Handloom Kasavu Saree Set (3 pieces)', 'Three traditional Kasavu sarees from Balaramapuram, worn once each for family functions. Blouse pieces included.', 2800.00, 'Like New', 'Thiruvananthapuram', 'placeholder-fashion.svg', 'active', 0, DATE_SUB(NOW(), INTERVAL 11 DAY)),
(13, 3, 7,  'Honda Activa 5G (2018)', 'Single owner, 28,000 km on the clock. Service done every six months at an authorised centre. All papers clear, insurance valid till March.', 42000.00, 'Good', 'Kottayam', 'placeholder-vehicles.svg', 'active', 1, DATE_SUB(NOW(), INTERVAL 1 DAY)),
(14, 5, 7,  'Royal Enfield Classic 350 (2017)', 'Well maintained, new tyres and battery. Second owner, 41,000 km. Test ride possible on weekends.', 98000.00, 'Good', 'Pathanamthitta', 'placeholder-vehicles.svg', 'active', 0, DATE_SUB(NOW(), INTERVAL 14 DAY)),
(15, 8, 8,  'LG 7kg Front Load Washing Machine', 'Inverter direct drive, six motion wash. Three years old and serviced in January. Installation help available within Kochi.', 14500.00, 'Good', 'Kochi', 'placeholder-home-appliances.svg', 'active', 0, DATE_SUB(NOW(), INTERVAL 8 DAY)),
(16, 4, 8,  'Prestige Induction Cooktop', 'Barely used 2000W induction cooktop with push buttons. Original box and manual included.', 1800.00, 'Like New', 'Kozhikode', 'placeholder-home-appliances.svg', 'active', 0, DATE_SUB(NOW(), INTERVAL 16 DAY)),
(17, 9, 9,  'Yonex Badminton Racket Pair with Kit Bag', 'Two Yonex Astrox rackets with a thermal kit bag and a box of shuttles. Strings were changed last month.', 1500.00, 'Good', 'Kottayam', 'placeholder-sports.svg', 'active', 0, DATE_SUB(NOW(), INTERVAL 10 DAY)),
(18, 2, 9,  'Hercules Gear Cycle (21 speed)', 'Mountain bike with front suspension, ridden for a year. Sold to a college student, listing kept for records.', 5500.00, 'Good', 'Kochi', 'placeholder-sports.svg', 'sold', 0, DATE_SUB(NOW(), INTERVAL 25 DAY)),
(19, 5, 1,  'Samsung 43 inch Smart LED TV', 'Full HD smart TV with Netflix and YouTube apps. Remote and wall mount included. Picture is crisp, no dead pixels.', 16000.00, 'Good', 'Pathanamthitta', 'placeholder-electronics.svg', 'active', 1, DATE_SUB(NOW(), INTERVAL 13 DAY)),
(20, 6, 1,  'Sony WH-1000XM3 Wireless Headphones', 'Industry leading noise cancellation. New ear pads fitted. Carry case and cables included.', 9000.00, 'Like New', 'Thiruvananthapuram', 'placeholder-electronics.svg', 'active', 0, DATE_SUB(NOW(), INTERVAL 17 DAY)),
(21, 10, 10,'Acoustic Guitar with Gig Bag', 'Beginner friendly acoustic guitar with a padded gig bag, tuner and three picks. Strings recently replaced.', 3800.00, 'Good', 'Kozhikode', 'placeholder-other.svg', 'active', 0, DATE_SUB(NOW(), INTERVAL 19 DAY)),
(22, 7, 6,  'Branded Watch (Unverified)', 'Listing removed by the admin because the seller could not prove the watch was genuine.', 1200.00, 'Good', 'Ernakulam', 'placeholder-fashion.svg', 'removed', 0, DATE_SUB(NOW(), INTERVAL 22 DAY));

INSERT INTO wishlist (user_id, product_id, created_at) VALUES
(2, 4,  DATE_SUB(NOW(), INTERVAL 2 DAY)),
(2, 13, DATE_SUB(NOW(), INTERVAL 1 DAY)),
(2, 7,  DATE_SUB(NOW(), INTERVAL 3 DAY)),
(3, 1,  DATE_SUB(NOW(), INTERVAL 1 DAY)),
(3, 20, DATE_SUB(NOW(), INTERVAL 5 DAY)),
(4, 1,  DATE_SUB(NOW(), INTERVAL 2 DAY)),
(4, 15, DATE_SUB(NOW(), INTERVAL 4 DAY)),
(6, 13, DATE_SUB(NOW(), INTERVAL 1 DAY)),
(8, 4,  DATE_SUB(NOW(), INTERVAL 2 DAY)),
(9, 19, DATE_SUB(NOW(), INTERVAL 6 DAY)),
(10, 7, DATE_SUB(NOW(), INTERVAL 3 DAY)),
(11, 4, DATE_SUB(NOW(), INTERVAL 1 DAY)),
(7, 1,  DATE_SUB(NOW(), INTERVAL 1 DAY));

INSERT INTO inquiries (product_id, sender_id, message, is_read, created_at) VALUES
(1,  3,  'Hi Anu, is the iPhone 12 still available? Can you do 26,500 if I pick it up this weekend?', 0, DATE_SUB(NOW(), INTERVAL 1 DAY)),
(1,  4,  'Does the phone have any repair history? Please share the IMEI if possible.', 1, DATE_SUB(NOW(), INTERVAL 2 DAY)),
(4,  2,  'Is the Dell laptop battery still giving 4 hours? I can come to Kozhikode on Saturday.', 0, DATE_SUB(NOW(), INTERVAL 2 DAY)),
(4,  8,  'Hello, does the price include the laptop bag? Can I see it before buying?', 1, DATE_SUB(NOW(), INTERVAL 3 DAY)),
(13, 2,  'Interested in the Activa. Are the RC book and insurance in your name?', 0, DATE_SUB(NOW(), INTERVAL 1 DAY)),
(13, 6,  'Can I test ride the Activa tomorrow evening? I will bring a mechanic along.', 1, DATE_SUB(NOW(), INTERVAL 2 DAY)),
(7,  10, 'Is the sofa price negotiable? I can arrange a tempo for pickup from Pathanamthitta.', 0, DATE_SUB(NOW(), INTERVAL 3 DAY)),
(15, 4,  'Is the washing machine still under warranty? Please share the bill date.', 0, DATE_SUB(NOW(), INTERVAL 4 DAY)),
(19, 9,  'Would you consider 14,500 for the Samsung TV? I will collect it myself.', 1, DATE_SUB(NOW(), INTERVAL 5 DAY)),
(20, 3,  'Are the Sony headphones still available? I would like to hear them before buying.', 0, DATE_SUB(NOW(), INTERVAL 4 DAY));

INSERT INTO reports (product_id, reporter_id, reason, details, status, created_at, resolved_at) VALUES
(22, 2,  'Suspected scam',          'The watch photos look copied from a shopping website. Seller refused to share more pictures.', 'resolved',  DATE_SUB(NOW(), INTERVAL 21 DAY), DATE_SUB(NOW(), INTERVAL 20 DAY)),
(14, 6,  'Wrong category',          'Motorcycle listings are fine, but the engine details in the description look inconsistent.',   'pending',   DATE_SUB(NOW(), INTERVAL 2 DAY),  NULL),
(2,  9,  'Spam or fake listing',    'Seems to be a duplicate of another listing posted last week.',                                 'dismissed', DATE_SUB(NOW(), INTERVAL 8 DAY),  DATE_SUB(NOW(), INTERVAL 7 DAY)),
(21, 4,  'Other',                   'Price looks too high compared to similar guitars. Please review.',                              'pending',   DATE_SUB(NOW(), INTERVAL 1 DAY),  NULL),
(6,  10, 'Inappropriate content',   'Description contains a personal phone number and asks buyers to avoid the website.',            'pending',   DATE_SUB(NOW(), INTERVAL 3 DAY),  NULL);
