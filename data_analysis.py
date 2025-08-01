import csv
import mariadb
import matplotlib.pyplot as plt
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database connection settings
config = {
    'host': os.getenv('DATABASE_HOST'),
    'user': os.getenv('DATABASE_USER'),
    'password': os.getenv('DATABASE_PW'),
    'database': os.getenv('DATABASE_NAME')
}

# Establish database connection
conn = mariadb.connect(**config)
cursor = conn.cursor()

# Execute SQL query to retrieve top types and their counts
cursor.execute("""
    SELECT typecode, COUNT(*) as count
    FROM callsigns
    WHERE typecode is not NULL
    AND typecode != ''
    AND first_message_received < '2025-05-17'
    AND first_message_received > '2025-02-17'
    GROUP BY typecode
    ORDER BY count DESC
    LIMIT 30
""")
top_types = cursor.fetchall()

# Extract top types
top_types_list = [row[0] for row in top_types]

# Execute SQL query to retrieve count of top 5 types
cursor.execute("""
    SELECT typecode, COUNT(*) as count
    FROM callsigns
    WHERE typecode IN ({})
    AND first_message_received < '2025-05-17'
    AND first_message_received > '2025-02-17'
    GROUP BY typecode
    ORDER BY count
""".format(','.join(['%s'] * len(top_types_list))), top_types_list)
top_types_counts = cursor.fetchall()

cursor.execute("""
    SELECT COUNT(*) as count
    FROM callsigns
    WHERE typecode NOT IN ({})
    AND first_message_received < '2025-05-17'
    AND first_message_received > '2025-02-17'
""".format(','.join(['%s'] * len(top_types_list))), top_types_list)
misc_count = cursor.fetchone()[0]

# Execute SQL query to retrieve types and counts for Misc group
cursor.execute("""
    SELECT typecode, COUNT(*) as count
    FROM callsigns
    WHERE typecode NOT IN ({})
    AND first_message_received < '2025-05-17'
    AND first_message_received > '2025-02-17'
    GROUP BY typecode
    ORDER BY count DESC
""".format(','.join(['%s'] * len(top_types_list))), top_types_list)
misc_types_counts = cursor.fetchall()

cursor.execute("""
    SELECT operator, COUNT(*) as count
    FROM callsigns
    WHERE first_message_received < '2025-05-17'
    AND first_message_received > '2025-02-17'
    and operator != ''
    GROUP BY operator
    ORDER BY count DESC
    LIMIT 30
""")
operators = cursor.fetchall()

# Close database connection
conn.close()

# Load the CSV file
with open('aircraftDatabase.csv', 'r') as f:
    reader = csv.DictReader(f)
    aircraft_data = {}
    for row in reader:
        typecode = row['typecode']
        if typecode and typecode not in aircraft_data:
            aircraft_data[typecode] = {
                'manufacturer': row['manufacturername'],
                'model': row['model']
            }

# Map the ICAO typecodes to their corresponding aircraft names
misc_types_counts_with_names = []
for row in misc_types_counts:
    typecode = row[0]
    if typecode in aircraft_data:
        name = f"{aircraft_data[typecode]['manufacturer']} {aircraft_data[typecode]['model']}"
    else:
        name = typecode
    misc_types_counts_with_names.append((typecode, name, row[1]))

# Save the table to a CSV file
with open('misc_planes.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['ICAO Type Code', 'Aircraft Type', 'Count'])
    writer.writerows(misc_types_counts_with_names)

# Create lists for bar chart
labels_top_5 = [f"{row[0]} ({row[1]})" for row in top_types_counts] + [f"Misc ({misc_count})"]
sizes_top_5 = [row[1] for row in top_types_counts] + [misc_count]

# Create bar chart
plt.figure(figsize=(10, 6))
plt.barh(labels_top_5, sizes_top_5)
plt.xlabel('Count')
plt.ylabel('Type')
plt.title('Top Types and Misc')
plt.tight_layout()
plt.show()

# Extract data for top operators
labels_top_operators = [f"{row[0]} ({row[1]})" for row in operators]
sizes_top_operators = [row[1] for row in operators]

# Create bar chart
plt.figure(figsize=(10, 6))
plt.barh(labels_top_operators, sizes_top_operators)
plt.xlabel('Count')
plt.ylabel('Operator')
plt.title('Top Operators')
plt.gca().invert_yaxis()
plt.tight_layout()
plt.show()
