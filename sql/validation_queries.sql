-- Validate chat logs were recorded

SELECT *
FROM chatbot_logs
WHERE response_time < 2000;


-- Validate no failed transactions

SELECT *
FROM chatbot_logs
WHERE status = 'FAILED';
