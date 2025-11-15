use dvd;

-- 1. Identifying Top Spenders.
SELECT 
    FULLNAME, 
    customer_id, 
    total_spent
FROM 
    (
        SELECT 
            CONCAT(c.first_name, ' ', c.last_name) AS FULLNAME,  -- Combine first and last names
            p.customer_id,                                        -- Customer ID
            SUM(p.amount) AS total_spent                          -- Total money spent by the customer
        FROM 
            customer c                                            -- From the customer table
        JOIN 
            payment p ON c.customer_id = p.customer_id            -- Join with the payment table on customer_id
        GROUP BY 
            p.customer_id, CONCAT(c.first_name, ' ', c.last_name) -- Group by customer ID and FULLNAME
        ORDER BY 
            total_spent DESC                                      -- Order by total money spent in descending order
        LIMIT 3                                                   -- Limit the results to the top 3 spenders
    ) AS Derived_table;                                           -- Alias the subquery as Derived_table
    
-- 2. Analyzing Monthly Rentals per Store.
SELECT 
    s.store_id, 
    YEAR(r.rental_date) AS rental_year, 
    MONTH(r.rental_date) AS rental_month, 
    COUNT(r.rental_id) AS rental_count
FROM 
    rental r
JOIN 
    staff st ON r.staff_id = st.staff_id
JOIN 
    store s ON st.store_id = s.store_id
GROUP BY 
    s.store_id, rental_year, rental_month
ORDER BY 
    s.store_id, rental_year, rental_month;
    
    
-- 3. Analyzing Film Categories and Rental Durations.
-- Define the Common Table Expression (CTE) named t1
WITH t1 AS (
    SELECT 
        f.title AS film_title, 
        c.name AS category_name, 
        NTILE(4) OVER (ORDER BY f.rental_duration) AS standard_quartile
    FROM 
        film f
    JOIN 
        film_category fc ON f.film_id = fc.film_id
    JOIN 
        category c ON fc.category_id = c.category_id
)

-- Main query to select distinct rows
SELECT 
    category_name, 
    standard_quartile, 
    COUNT(film_title) AS film_count
FROM 
    t1
WHERE 
    category_name IN ('Animation', 'Children', 'Classics', 'Comedy', 'Family', 'Music')
GROUP BY 
    category_name, 
    standard_quartile
ORDER BY 
    category_name, 
    standard_quartile;
    
-- 4. Analyzing Top 10 Paying Customers' Payment Patterns.
-- Define the CTE to find the top 10 paying customers
WITH top_paying_customers AS (
    SELECT 
        c.customer_id, 
        CONCAT(c.first_name, ' ', c.last_name) AS customer_name, 
        SUM(p.amount) AS total_payment
    FROM 
        customer c
    JOIN 
        payment p ON c.customer_id = p.customer_id
    GROUP BY 
        c.customer_id, customer_name
    ORDER BY 
        total_payment DESC
    LIMIT 10
)

-- Main query to analyze payment patterns
SELECT 
    tpc.customer_name, 
    DATE_FORMAT(p.payment_date, '%Y-%m') AS payment_month, 
    COUNT(p.payment_id) AS payment_count, 
    SUM(p.amount) AS total_amount
FROM 
    payment p
JOIN 
    top_paying_customers tpc ON p.customer_id = tpc.customer_id
GROUP BY 
    tpc.customer_name, payment_month
ORDER BY 
    tpc.customer_name, payment_month;

-- 5. Family Movie Rental Analysis.    
-- Define the CTE to select relevant columns
WITH t1 AS (
    SELECT 
        f.title AS film_title, 
        c.name AS category_name, 
        r.rental_id
    FROM 
        film f
    JOIN 
        film_category fc ON f.film_id = fc.film_id
    JOIN 
        category c ON fc.category_id = c.category_id
    JOIN 
        inventory i ON f.film_id = i.film_id
    JOIN 
        rental r ON i.inventory_id = r.inventory_id
)

-- Main query to analyze the rentals
SELECT 
    film_title, 
    category_name, 
    COUNT(rental_id) AS rental_count
FROM 
    t1
WHERE 
    category_name IN ('Animation', 'Children', 'Classics', 'Comedy', 'Family', 'Music')
GROUP BY 
    film_title, category_name
ORDER BY 
    category_name, film_title;
    
-- 6. Identifying Peak Activity by Store.
-- Define the CTE to select relevant columns and count rentals for each month and store
WITH result_table AS (
    SELECT 
        YEAR(rental_date) AS YEAR, 
        MONTH(rental_date) AS RENTAL_MONTH, 
        store_id, 
        COUNT(rental_id) AS rental_count
    FROM 
        rental RE
    JOIN 
        staff ST ON RE.staff_id = ST.staff_id
    GROUP BY 
        YEAR(rental_date), MONTH(rental_date), store_id
    ORDER BY 
        YEAR, RENTAL_MONTH
)

-- Main query to sum counts for each store separately
SELECT 
    YEAR, 
    RENTAL_MONTH, 
    SUM(IF(store_id = 1, rental_count, 0)) AS store_1_count,
    SUM(IF(store_id = 2, rental_count, 0)) AS store_2_count
FROM 
    result_table
GROUP BY 
    YEAR, RENTAL_MONTH
ORDER BY 
    YEAR, RENTAL_MONTH;
   
-- 7.Analyzing Total Rental Orders for Family-Friendly Film Categories.
-- Define the CTE to select relevant columns and count rentals for each film category
WITH result_table AS (
    SELECT 
        f.title AS film_title, 
        cat.name AS category_name, 
        COUNT(re.rental_id) AS num_rentals
    FROM 
        film f
    JOIN 
        film_category fc ON f.film_id = fc.film_id
    JOIN 
        category cat ON fc.category_id = cat.category_id
    JOIN 
        inventory inv ON f.film_id = inv.film_id
    JOIN 
        rental re ON inv.inventory_id = re.inventory_id
    WHERE 
        cat.name IN ('Animation', 'Children', 'Classics', 'Comedy', 'Family', 'Music')
    GROUP BY 
        film_title, category_name
)

-- 8. Total Revenue by Category Report.
-- Main query to sum rental counts for each film category
SELECT 
    category_name, 
    SUM(num_rentals) AS total
FROM 
    result_table
GROUP BY 
    category_name
ORDER BY 
    total DESC;
    
SELECT 
    category.name, 
    SUM(payment.amount) AS Total_revenue
FROM 
    category
JOIN 
    film_category ON category.category_id = film_category.category_id
JOIN 
    film ON film_category.film_id = film.film_id
JOIN 
    inventory ON film.film_id = inventory.film_id
JOIN 
    rental ON inventory.inventory_id = rental.inventory_id
JOIN 
    payment ON rental.rental_id = payment.rental_id
GROUP BY 
    category.name;
    
-- 9. Total Rentals and Average Rental Rate.
SELECT 
    customer.first_name, 
    customer.last_name, 
    customer.email, 
    COUNT(rental.rental_id) AS total_rentals, 
    AVG(payment.amount) AS average_rental_rate
FROM 
    customer
LEFT JOIN 
    rental ON customer.customer_id = rental.customer_id
LEFT JOIN 
    payment ON rental.rental_id = payment.rental_id
GROUP BY 
    customer.first_name, 
    customer.last_name, 
    customer.email;
 
 -- 10. Highly Rented Films Analysis.
SELECT 
    film.title, 
    COUNT(DISTINCT rental.rental_id) AS rental_count
FROM 
    film
JOIN 
    inventory ON film.film_id = inventory.film_id
JOIN 
    rental ON inventory.inventory_id = rental.inventory_id
GROUP BY 
    film.title
HAVING 
    rental_count > 30;
    
-- 11. Analyzing City Rental Rates.
-- Common Table Expression (CTE) to calculate average rental rates for each city
WITH CityRentalRates AS (
    SELECT 
        city.city_id, 
        city.city, 
        AVG(payment.amount) AS avg_rental_rate
    FROM 
        city
    JOIN 
        address ON city.city_id = address.city_id
    JOIN 
        customer ON address.address_id = customer.address_id
    JOIN 
        rental ON customer.customer_id = rental.customer_id
    JOIN 
        payment ON rental.rental_id = payment.rental_id
    GROUP BY 
        city.city_id, city.city
),

-- Common Table Expression (CTE) to find maximum and minimum rental rates
MaxMinRates AS (
    SELECT 
        MAX(avg_rental_rate) AS max_rate, 
        MIN(avg_rental_rate) AS min_rate
    FROM 
        CityRentalRates
)

-- Main query to determine rate status and cross join with MaxMinRates CTE
SELECT 
    cr.city, 
    cr.avg_rental_rate,
    CASE 
        WHEN cr.avg_rental_rate = mmr.max_rate THEN 'Highest Rate'
        WHEN cr.avg_rental_rate = mmr.min_rate THEN 'Lowest Rate'
        ELSE 'Standard Rate'
    END AS rate_status
FROM 
    CityRentalRates cr
CROSS JOIN 
    MaxMinRates mmr;
    
-- 12. Identifying Top Customers: Unique Film Rentals.
SELECT 
    customer.customer_id, 
    customer.first_name, 
    customer.last_name, 
    customer.email, 
    COUNT(DISTINCT rental.inventory_id) AS unique_films_rented
FROM 
    customer
JOIN 
    rental ON customer.customer_id = rental.customer_id
GROUP BY 
    customer.customer_id, 
    customer.first_name, 
    customer.last_name, 
    customer.email
ORDER BY 
    unique_films_rented DESC
LIMIT 3;

-- 13. Analysis of Monthly Revenue Trends
SELECT 
    DATE_FORMAT(payment.payment_date, '%Y-%m') AS payment_month,
    SUM(payment.amount) AS monthly_revenue
FROM 
    payment
GROUP BY 
    payment_month
ORDER BY 
    payment_month;
    
 -- 14. Identifying Most Active Stores    
SELECT 
    store.store_id,
    COUNT(rental.rental_id) AS total_rentals
FROM 
    store
LEFT JOIN 
    staff ON store.store_id = staff.store_id
LEFT JOIN 
    rental ON staff.staff_id = rental.staff_id
GROUP BY 
    store.store_id
ORDER BY 
    total_rentals DESC
LIMIT 5;

-- 15. Analysis of Customer Lifetime Value
SELECT 
    customer.customer_id,
    customer.first_name,
    customer.last_name,
    COUNT(rental.rental_id) AS total_rentals,
    SUM(payment.amount) AS total_spent
FROM 
    customer
LEFT JOIN 
    rental ON customer.customer_id = rental.customer_id
LEFT JOIN 
    payment ON rental.rental_id = payment.rental_id
GROUP BY 
    customer.customer_id,
    customer.first_name,
    customer.last_name
ORDER BY 
    total_spent DESC
LIMIT 5;

-- 16. Identifying Customer Loyalty Tiers based on Rental Frequency
SELECT 
    customer.customer_id,
    customer.first_name,
    customer.last_name,
    COUNT(rental.rental_id) AS total_rentals,
    CASE 
        WHEN COUNT(rental.rental_id) >= 50 THEN 'Platinum'
        WHEN COUNT(rental.rental_id) >= 30 THEN 'Gold'
        WHEN COUNT(rental.rental_id) >= 10 THEN 'Silver'
        ELSE 'Bronze'
    END AS loyalty_tier
FROM 
    customer
LEFT JOIN 
    rental ON customer.customer_id = rental.customer_id
GROUP BY 
    customer.customer_id,
    customer.first_name,
    customer.last_name
ORDER BY 
    total_rentals DESC;
    
-- 17. Analyzing Monthly Revenue Growth Rate
WITH MonthlyRevenue AS (
    SELECT 
        DATE_FORMAT(payment_date, '%Y-%m') AS payment_month,
        SUM(amount) AS monthly_revenue
    FROM 
        payment
    GROUP BY 
        payment_month
),
RevenueGrowth AS (
    SELECT 
        payment_month,
        monthly_revenue,
        LAG(monthly_revenue) OVER (ORDER BY payment_month) AS prev_monthly_revenue,
        (monthly_revenue - LAG(monthly_revenue) OVER (ORDER BY payment_month)) / LAG(monthly_revenue) OVER (ORDER BY payment_month) AS growth_rate
    FROM 
        MonthlyRevenue
)
SELECT 
    payment_month,
    monthly_revenue,
    IFNULL(growth_rate, 0) AS growth_rate
FROM 
    RevenueGrowth;
    
-- 18. 
SELECT 
    fc.category_id,
    c.name AS category_name,
    SUM(payment.amount) AS total_revenue,
    SUM(f.rental_duration * payment.amount) AS total_cost,
    SUM(payment.amount) - SUM(f.rental_duration * payment.amount) AS profit,
    (SUM(payment.amount) - SUM(f.rental_duration * payment.amount)) / SUM(f.rental_duration * payment.amount) * 100 AS ROI_percentage
FROM 
    payment
JOIN 
    rental ON payment.rental_id = rental.rental_id
JOIN 
    inventory i ON rental.inventory_id = i.inventory_id
JOIN 
    film f ON i.film_id = f.film_id
JOIN 
    film_category fc ON f.film_id = fc.film_id
JOIN 
    category c ON fc.category_id = c.category_id
GROUP BY 
    fc.category_id, c.name
ORDER BY 
    profit DESC;
    
-- 19. Analysis of Rental Patterns Over Time
WITH RentalPatterns AS (
    SELECT 
        DATE_FORMAT(rental_date, '%Y-%m') AS rental_month,
        COUNT(rental_id) AS rental_count
    FROM 
        rental
    GROUP BY 
        rental_month
)
SELECT 
    rental_month,
    rental_count,
    LAG(rental_count) OVER (ORDER BY rental_month) AS prev_rental_count,
    (rental_count - LAG(rental_count) OVER (ORDER BY rental_month)) AS rental_growth
FROM 
    RentalPatterns;
    
-- 20.Analysis of Late Returns Impact on Revenue
SELECT 
    CASE 
        WHEN DATEDIFF(return_date, rental_date) > rental_duration THEN 'Late'
        ELSE 'On Time'
    END AS return_status,
    COUNT(rental.rental_id) AS rental_count,
    SUM(payment.amount) AS total_revenue
FROM 
    rental
JOIN 
    payment ON rental.rental_id = payment.rental_id
JOIN 
    inventory ON rental.inventory_id = inventory.inventory_id
JOIN 
    film ON inventory.film_id = film.film_id
GROUP BY 
    return_status;
 
-- 21. dentifying Most Popular Film Genres by Rental Frequency
SELECT 
    category.name AS genre,
    COUNT(rental.rental_id) AS rental_count
FROM 
    rental
JOIN 
    inventory ON rental.inventory_id = inventory.inventory_id
JOIN 
    film ON inventory.film_id = film.film_id
JOIN 
    film_category ON film.film_id = film_category.film_id
JOIN 
    category ON film_category.category_id = category.category_id
GROUP BY 
    genre
ORDER BY 
    rental_count DESC;

-- 22. Analysis of Rental Return Patterns by Day of the Week    
SELECT 
    DAYNAME(return_date) AS day_of_week,
    COUNT(rental_id) AS rental_count
FROM 
    rental
WHERE 
    return_date IS NOT NULL
GROUP BY 
    day_of_week
ORDER BY 
    FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday');
    
-- 23. Analysis of Revenue Distribution Across Store Locations
SELECT 
    city.city,
    SUM(payment.amount) AS total_revenue
FROM 
    payment
JOIN 
    rental ON payment.rental_id = rental.rental_id
JOIN 
    inventory ON rental.inventory_id = inventory.inventory_id
JOIN 
    store ON inventory.store_id = store.store_id
JOIN 
    address ON store.address_id = address.address_id
JOIN 
    city ON address.city_id = city.city_id
GROUP BY 
    city.city
ORDER BY 
    total_revenue DESC;

-- 24. Identifying Most Profitable Actors    
SELECT 
    actor.actor_id,
    actor.first_name,
    actor.last_name,
    SUM(payment.amount) AS total_revenue
FROM 
    actor
JOIN 
    film_actor ON actor.actor_id = film_actor.actor_id
JOIN 
    film ON film_actor.film_id = film.film_id
JOIN 
    inventory ON film.film_id = inventory.film_id
JOIN 
    rental ON inventory.inventory_id = rental.inventory_id
JOIN 
    payment ON rental.rental_id = payment.rental_id
GROUP BY 
    actor.actor_id,
    actor.first_name,
    actor.last_name
ORDER BY 
    total_revenue DESC;

-- 25. Analysis of Film Availability and Demand    
SELECT 
    f.title AS film_title,
    COUNT(i.inventory_id) AS available_copies,
    COUNT(r.rental_id) AS rental_count
FROM 
    film f
LEFT JOIN 
    inventory i ON f.film_id = i.film_id
LEFT JOIN 
    rental r ON i.inventory_id = r.inventory_id
GROUP BY 
    film_title
ORDER BY 
    rental_count DESC, available_copies DESC;