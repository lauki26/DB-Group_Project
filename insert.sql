INSERT INTO institution VALUES
(1, 'Johns Hopkins University', 'University'),
(2, 'New York University', 'University'),
(3, 'National Institutes of Health', 'Government'),
(4, 'Pfizer', 'Private'),
(5, 'Harvard University', 'University');


INSERT INTO researcher VALUES
(1, 'Dr. Alice Chen', 'alice@jhu.edu', 1),
(2, 'Dr. Bob Lee', 'bob@nyu.edu', 2),
(3, 'Dr. John Doe', 'john@nih.gov', 3),
(4, 'Dr. James Park', 'james@pfizer.com', 4),
(5, 'Dr. Maria Gomez', 'maria@jhu.edu', 1),
(6, 'Dr. John Carter', 'john@harvard.edu', 5),
(7, 'Dr. Emily Wong', 'emily@nyu.edu', 2),
(8, 'Dr. Raj Patel', 'raj@nih.gov', 3),
(9, 'Dr. Laura Smith', 'laura@pfizer.com', 4),
(10, 'Dr. Kevin Brown', 'kevin@jhu.edu', 1);

INSERT INTO experiment VALUES
(1, 'Cancer Drug Trial', '2025-01-10', '2025-03-20', 'Testing treatment'),
(2, 'AI Diagnostics', '2025-02-01', '2025-05-15', 'AI imaging'),
(3, 'Vaccine Study', '2025-01-25', '2025-04-10', 'Vaccine trial'),
(4, 'Neuroscience Study', '2025-03-01', '2025-06-01', 'Brain research'),
(5, 'Genetics Mapping', '2025-02-15', '2025-04-30', 'DNA analysis'),
(6, 'Robotics Surgery', '2025-03-10', '2025-05-20', 'Surgical robots');

INSERT INTO role VALUES
(1, 'Lead'),
(2, 'Contributor'),
(3, 'Assistant');

INSERT INTO researcher_experiment VALUES
(1,1,1),  
(1,2,2),
(1,4,2),
(2,2,1),
(2,5,2),
(3,1,2),
(3,3,1),
(3,5,2),
(4,3,2),
(4,6,1),
(5,4,1),
(6,5,1),
(7,2,2),
(8,3,2),
(9,6,2),
(10,1,2),
(10,6,2);

INSERT INTO funding_source VALUES
(1, 'NIH Grant', 'Government'),
(2, 'Private Investment', 'Private'),
(3, 'University Fund', 'Academic'),
(4, 'Pharma Sponsor', 'Private'),
(5, 'Tech Grant', 'Government');

INSERT INTO experiment_funding_source VALUES
(1,1),
(1,4),
(2,2),
(2,3),
(2,4),
(3,1),
(3,5),
(4,3),
(5,1),
(5,2),
(5,3),
(6,4),
(6,5);

INSERT INTO charge VALUES
(1,1,5000,'2025-01-15','2025-02-15','Equipment'),
(2,2,8000,'2025-02-10','2025-03-10','Software'),
(3,3,6000,'2025-02-20','2025-03-25','Lab'),
(4,4,7000,'2025-03-10','2025-04-10','Staff'),
(5,5,6500,'2025-02-25','2025-03-30','Materials'),
(6,6,9000,'2025-03-20','2025-04-25','Robotics'),
(7,1,3000,'2025-03-01','2025-03-31','Maintenance'),
(8,2,4000,'2025-03-15','2025-04-15','Cloud');

INSERT INTO charge_adjustment VALUES
(1,1,'Discount',-500,'2025-02-01'),
(2,2,'Extra Cost',1000,'2025-03-05'),
(3,3,'Correction',-300,'2025-03-15'),
(4,4,'Bonus Funding',1200,'2025-04-01'),
(5,5,'Discount',-200,'2025-03-10'),
(6,6,'Extra Cost',1500,'2025-04-05'),
(7,7,'Correction',-100,'2025-03-20'),
(8,8,'Bonus Funding',800,'2025-04-10');

INSERT INTO facility VALUES
(1, 1, 'Cancer Research Lab', 'Laboratory', 'Spring 2025', 200),
(2, 2, 'AI Computing Center', 'Computing', 'Spring 2025', 300),
(3, 3, 'Vaccine Testing Facility', 'Laboratory', 'Summer 2025', 250),
(4, 4, 'Robotics Surgery Room', 'Medical', 'Spring 2025', 400),
(5, 5, 'Genetics Analysis Lab', 'Laboratory', 'Fall 2025', 220);

INSERT INTO experiment_facility VALUES
(1, 1, 1, '2025-01-15', '2025-02-15'),
(2, 2, 2, '2025-02-10', '2025-03-20'),
(3, 3, 3, '2025-02-20', '2025-03-30'),
(4, 4, 1, '2025-03-10', '2025-04-20'),
(5, 6, 4, '2025-03-20', '2025-04-30');

INSERT INTO equipment VALUES
(1, 'MRI Scanner', 'Brain Imaging', 'Shared', 'Fixed', 500),
(2, 'DNA Sequencer', 'Genetic Analysis', 'Dedicated', 'Fixed', 450),
(3, 'Surgical Robot', 'Robot-Assisted Surgery', 'Shared', 'Movable', 700),
(4, 'Microscope', 'Cell Observation', 'Shared', 'Movable', 150),
(5, 'GPU Cluster', 'AI Training', 'Dedicated', 'Fixed', 600);

INSERT INTO experiment_equipment VALUES
(1, 1, 4, '2025-01-15', '2025-02-10'),
(2, 2, 5, '2025-02-10', '2025-03-15'),
(3, 3, 2, '2025-02-20', '2025-03-25'),
(4, 4, 1, '2025-03-10', '2025-04-10'),
(5, 6, 3, '2025-03-20', '2025-04-25');




