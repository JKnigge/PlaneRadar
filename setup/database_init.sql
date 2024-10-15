/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8 */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

CREATE DATABASE IF NOT EXISTS `planeradar` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;
USE `planeradar`;

CREATE TABLE IF NOT EXISTS `callsigns` (
  `id` int NOT NULL AUTO_INCREMENT,
  `hex_ident` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `callsign` varchar(50) NOT NULL,
  `first_message_generated` datetime DEFAULT NULL,
  `first_message_received` datetime NOT NULL DEFAULT (now()),
  `last_message_generated` datetime DEFAULT NULL,
  `last_message_received` datetime DEFAULT NULL,
  `registration` varchar(50) DEFAULT NULL,
  `typecode` varchar(50) DEFAULT NULL,
  `operator` varchar(50) DEFAULT NULL,
  `num_messages` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `positions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `hex_ident` varchar(50) DEFAULT NULL,
  `callsign_id` int NOT NULL,
  `latitude` float DEFAULT NULL,
  `longitude` float DEFAULT NULL,
  `altitude` int DEFAULT NULL,
  `distance` float DEFAULT NULL,
  `bearing` float DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `positions.callsign` (`callsign_id`) USING BTREE,
  CONSTRAINT `positions.callsign` FOREIGN KEY (`callsign_id`) REFERENCES `callsigns` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;
