-- Each query starts with a "-- name:" marker so analysis.py can load it.

-- name: headcount_by_department
-- Headcount per department (JOIN + GROUP BY + aggregate)
SELECT d.dept_name,
       COUNT(e.emp_id)                    AS headcount,
       ROUND(AVG(e.salary), 0)            AS avg_salary
FROM departments d
LEFT JOIN employees e ON e.dept_id = d.dept_id AND e.status = 'Active'
GROUP BY d.dept_name
ORDER BY headcount DESC;

-- name: attendance_rate_by_department
-- Overall attendance % per department
SELECT d.dept_name,
       COUNT(*)                                                    AS records,
       SUM(a.status = 'Absent')                                    AS absences,
       SUM(a.status = 'Late')                                      AS late_arrivals,
       ROUND(100.0 * SUM(a.status IN ('Present','Late','Half-Day')) / COUNT(*), 2) AS attendance_pct
FROM attendance a
JOIN employees   e ON e.emp_id  = a.emp_id
JOIN departments d ON d.dept_id = e.dept_id
GROUP BY d.dept_name
ORDER BY attendance_pct DESC;

-- name: monthly_attendance_trend
-- Month-over-month attendance trend per department (uses the view)
SELECT dept_name, month, attendance_pct
FROM v_monthly_attendance
ORDER BY dept_name, month;

-- name: attendance_by_weekday
-- Which weekday has the most absences?  (0 = Sunday)
SELECT CASE strftime('%w', att_date)
           WHEN '1' THEN 'Monday'  WHEN '2' THEN 'Tuesday'
           WHEN '3' THEN 'Wednesday' WHEN '4' THEN 'Thursday'
           WHEN '5' THEN 'Friday' END                AS weekday,
       COUNT(*)                                       AS records,
       SUM(status = 'Absent')                         AS absences,
       ROUND(100.0 * SUM(status = 'Absent') / COUNT(*), 2) AS absence_pct
FROM attendance
GROUP BY strftime('%w', att_date)
ORDER BY strftime('%w', att_date);

-- name: below_average_attendance_departments
-- SUBQUERY: departments whose attendance is below the company average
SELECT dept_name, attendance_pct
FROM (
    SELECT d.dept_name,
           ROUND(100.0 * SUM(a.status IN ('Present','Late','Half-Day')) / COUNT(*), 2) AS attendance_pct
    FROM attendance a
    JOIN employees   e ON e.emp_id  = a.emp_id
    JOIN departments d ON d.dept_id = e.dept_id
    GROUP BY d.dept_name
) AS dept_stats
WHERE attendance_pct < (
    SELECT 100.0 * SUM(status IN ('Present','Late','Half-Day')) / COUNT(*) FROM attendance
)
ORDER BY attendance_pct;

-- name: employees_above_dept_avg_salary
-- CORRELATED SUBQUERY: employees paid above their own department's average
SELECT e.first_name || ' ' || e.last_name AS employee,
       d.dept_name,
       e.salary
FROM employees e
JOIN departments d ON d.dept_id = e.dept_id
WHERE e.salary > (SELECT AVG(salary) FROM employees WHERE dept_id = e.dept_id)
ORDER BY d.dept_name, e.salary DESC;

-- name: frequent_late_arrivals
-- HAVING: employees with 5 or more late arrivals
SELECT e.emp_id,
       e.first_name || ' ' || e.last_name AS employee,
       d.dept_name,
       COUNT(*) AS late_count
FROM attendance a
JOIN employees   e ON e.emp_id  = a.emp_id
JOIN departments d ON d.dept_id = e.dept_id
WHERE a.status = 'Late'
GROUP BY e.emp_id, employee, d.dept_name
HAVING COUNT(*) >= 5
ORDER BY late_count DESC
LIMIT 15;

-- name: top_performers
-- SUBQUERY: employees whose avg rating beats the company average
SELECT e.first_name || ' ' || e.last_name AS employee,
       d.dept_name,
       ROUND(AVG(r.rating), 2)        AS avg_rating,
       ROUND(AVG(r.goals_met_pct), 1) AS avg_goals_met
FROM performance_reviews r
JOIN employees   e ON e.emp_id  = r.emp_id
JOIN departments d ON d.dept_id = e.dept_id
GROUP BY e.emp_id, employee, d.dept_name
HAVING AVG(r.rating) > (SELECT AVG(rating) FROM performance_reviews)
ORDER BY avg_rating DESC, avg_goals_met DESC
LIMIT 10;

-- name: attendance_vs_performance
-- Does better attendance go with better performance?  (join two aggregates)
SELECT d.dept_name,
       ROUND(att.attendance_pct, 2) AS attendance_pct,
       ROUND(perf.avg_rating, 2)    AS avg_rating
FROM departments d
JOIN (SELECT e.dept_id,
             100.0 * SUM(a.status IN ('Present','Late','Half-Day')) / COUNT(*) AS attendance_pct
      FROM attendance a JOIN employees e ON e.emp_id = a.emp_id
      GROUP BY e.dept_id) att  ON att.dept_id  = d.dept_id
JOIN (SELECT e.dept_id, AVG(r.rating) AS avg_rating
      FROM performance_reviews r JOIN employees e ON e.emp_id = r.emp_id
      GROUP BY e.dept_id) perf ON perf.dept_id = d.dept_id
ORDER BY attendance_pct DESC;

-- name: salary_rank_within_department
-- WINDOW FUNCTION: rank employees by salary inside each department
SELECT dept_name, employee, salary, dept_rank
FROM (
    SELECT d.dept_name,
           e.first_name || ' ' || e.last_name AS employee,
           e.salary,
           RANK() OVER (PARTITION BY d.dept_id ORDER BY e.salary DESC) AS dept_rank
    FROM employees e
    JOIN departments d ON d.dept_id = e.dept_id
)
WHERE dept_rank <= 3
ORDER BY dept_name, dept_rank;

-- name: managers_and_team_size
-- SELF JOIN: each manager and the size of their team
SELECT m.first_name || ' ' || m.last_name AS manager,
       d.dept_name,
       COUNT(e.emp_id) AS direct_reports
FROM employees m
JOIN employees   e ON e.manager_id = m.emp_id
JOIN departments d ON d.dept_id    = m.dept_id
GROUP BY m.emp_id, manager, d.dept_name
ORDER BY direct_reports DESC;

-- name: department_headcount_by_hire_year
-- Hiring trend by year
SELECT strftime('%Y', hire_date) AS hire_year,
       COUNT(*)                  AS hires
FROM employees
GROUP BY hire_year
ORDER BY hire_year;
