PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS institution;
DROP TABLE IF EXISTS researcher;
DROP TABLE IF EXISTS experiment;
DROP TABLE IF EXISTS role;
DROP TABLE IF EXISTS researcher_experiment;
DROP TABLE IF EXISTS funding_source;
DROP TABLE IF EXISTS experiment_funding_source;
DROP TABLE IF EXISTS charge;
DROP TABLE IF EXISTS charge_adjustment;
DROP TABLE IF EXISTS facility;
DROP TABLE IF EXISTS experiment_facility;
DROP TABLE IF EXISTS equipment;
DROP TABLE IF EXISTS experiment_equipment;



CREATE TABLE institution (
    institutionId INTEGER PRIMARY KEY AUTOINCREMENT,
    institutionName TEXT NOT NULL,
    institutionType TEXT NOT NULL
);


CREATE TABLE researcher (
    researcherId INTEGER PRIMARY KEY,
    researcherName TEXT NOT NULL,
    contact TEXT NOT NULL,
    institutionId INTEGER NOT NULL,
    FOREIGN KEY (institutionId) REFERENCES institution(institutionId)
);


CREATE TABLE experiment (
    experimentId INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    startDate TEXT NOT NULL,
    endDate TEXT NOT NULL,
    description TEXT NOT NULL
);


 CREATE TABLE role (
    roleId INTEGER PRIMARY KEY,
    roleName TEXT NOT NULL
);


CREATE TABLE researcher_experiment (
    researcherId INTEGER NOT NULL,
    experimentId INTEGER NOT NULL,
    roleId INTEGER NOT NULL,
    FOREIGN KEY (researcherId) REFERENCES researcher(researcherId),
    FOREIGN KEY (experimentId) REFERENCES experiment(experimentId),
    FOREIGN KEY (roleId) REFERENCES role(roleId)
);


CREATE TABLE funding_source (
    fundingSourceId INTEGER PRIMARY KEY,
    fundingSourceName TEXT NOT NULL,
    fundingSourceType TEXT NOT NULL
);


CREATE TABLE experiment_funding_source (
    experimentId INTEGER NOT NULL, 
    fundingSourceId INTEGER NOT NULL, 
    FOREIGN KEY (experimentId) REFERENCES experiment(experimentId),
    FOREIGN KEY (fundingSourceId) REFERENCES funding_source(fundingSourceId)
);


CREATE TABLE charge (
    chargeId INTEGER PRIMARY KEY,
    experimentId INTEGER NOT NULL,
    chargeAmount INTEGER NOT NULL,
    startDate TEXT NOT NULL,
    endDate TEXT NOT NULL,
    chargeType TEXT NOT NULL,
    FOREIGN KEY (experimentId) REFERENCES experiment(experimentId)
);


CREATE TABLE charge_adjustment (
    adjustmentId INTEGER PRIMARY KEY,
    chargeId INTEGER NOT NULL,
    adjustmentType TEXT NOT NULL,
    amount INTEGER NOT NULL,
    adjustmentDate TEXT NOT NULL,
    FOREIGN KEY (chargeId) REFERENCES charge(chargeId)
);

CREATE TABLE facility (
    facilityId INTEGER PRIMARY KEY,
    institutionId INTEGER NOT NULL,
    facilityName TEXT NOT NULL,
    facilityType TEXT NOT NULL,
    term TEXT NOT NULL,
    hourlyRate INTEGER NOT NULL,
    FOREIGN KEY (institutionId) REFERENCES institution(institutionId)
);

CREATE TABLE experiment_facility (
    facilityUsageId INTEGER PRIMARY KEY,
    experimentId INTEGER NOT NULL,
    facilityId INTEGER NOT NULL,
    startDate TEXT NOT NULL,
    endDate TEXT NOT NULL,
    FOREIGN KEY (experimentId) REFERENCES experiment(experimentId),
    FOREIGN KEY (facilityId) REFERENCES facility(facilityId)
);

CREATE TABLE equipment (
    equipmentId INTEGER PRIMARY KEY,
    equipmentName TEXT NOT NULL,
    equipmentPurpose TEXT NOT NULL,
    sharingStatus TEXT NOT NULL,
    movability TEXT NOT NULL,
    hourlyRate INTEGER NOT NULL
);

CREATE TABLE experiment_equipment (
    equipmentUsageId INTEGER PRIMARY KEY,
    experimentId INTEGER NOT NULL,
    equipmentId INTEGER NOT NULL,
    startDate TEXT NOT NULL,
    endDate TEXT NOT NULL,
    FOREIGN KEY (experimentId) REFERENCES experiment(experimentId), 
    FOREIGN KEY (equipmentId) REFERENCES equipment(equipmentId)
);










