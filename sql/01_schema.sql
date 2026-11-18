-- Red String Blood Registry - MySQL / MariaDB schema.
-- Safe to run more than once (CREATE TABLE IF NOT EXISTS). Parent tables come first.

CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    email         VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS profiles (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    user_id          INT          NOT NULL UNIQUE,
    full_name        VARCHAR(100),
    location         VARCHAR(100),
    sex              VARCHAR(20),
    birthdate        DATE,
    blood_type       VARCHAR(10),
    bio              TEXT,
    picture_filename VARCHAR(255) NOT NULL DEFAULT 'default.jpg',
    is_public        TINYINT(1)   NOT NULL DEFAULT 1,
    CONSTRAINT fk_profiles_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS measurements (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT         NOT NULL,
    kind          VARCHAR(20) NOT NULL,          -- 'weight' or 'height'
    value         DOUBLE      NOT NULL,
    date_measured DATE        NOT NULL,
    CONSTRAINT fk_measurements_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS health_statuses (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT         NOT NULL,
    status       VARCHAR(50) NOT NULL,           -- 'Healthy' or 'Not Healthy'
    notes        TEXT,
    date_checked DATE        NOT NULL,
    CONSTRAINT fk_health_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS communities (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_by  INT          NOT NULL,
    CONSTRAINT fk_communities_creator FOREIGN KEY (created_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS community_members (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT       NOT NULL,
    community_id INT       NOT NULL,
    joined_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_member (user_id, community_id),
    CONSTRAINT fk_members_user      FOREIGN KEY (user_id)      REFERENCES users(id)       ON DELETE CASCADE,
    CONSTRAINT fk_members_community FOREIGN KEY (community_id) REFERENCES communities(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS donations (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT          NOT NULL,
    community_id INT          NULL,
    date_donated DATE         NOT NULL,
    location     VARCHAR(150) NOT NULL,
    event_name   VARCHAR(150),
    CONSTRAINT fk_donations_user      FOREIGN KEY (user_id)      REFERENCES users(id)       ON DELETE CASCADE,
    CONSTRAINT fk_donations_community FOREIGN KEY (community_id) REFERENCES communities(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS trivia_facts (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    category VARCHAR(50)  NOT NULL,
    title    VARCHAR(150) NOT NULL,
    body     TEXT         NOT NULL,
    source   VARCHAR(100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
