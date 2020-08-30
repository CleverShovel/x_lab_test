SELECT date, result, COUNT(*), SUM(duration) as general_duration, MAX(project.name) as project, MAX(server.name) as server
FROM log
INNER JOIN project ON project_id = project.id
INNER JOIN server ON server_id = server.id
GROUP BY date, result;