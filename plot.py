import pandas as pd
import matplotlib.pyplot as plt

# Load the data
#C:\Users\Admin\Downloads\Metro_Nashville_Police_Department_Incidents.csv
#schools = pd.read_csv('https://data.nashville.gov/Education/Metro-Nashville-Public-Schools-School-Directory/7qhq-4vgb')  # Make sure this file exists and has Longitude/Latitude columns

path_file = 'data/Metro_Nashville_Police_Department_Incidents.csv'
schools = pd.read_csv(path_file)  # Make sure this file exists and has Longitude/Latitude columns

"""['X', 'Y', 'OBJECTID', 'Primary_Key', 'Incident_Number', 'Report_Type',
       'Report_Type_Description', 'Incident_Status_Code',
       'Incident_Status_Description', 'Investigation_Status',
       'Incident_Location', 'Latitude', 'Longitude', 'RPA', 'Zone',
       'Location_Code', 'Location_Description', 'Offense_Number',
       'Offense_NIBRS', 'Offense_Description', 'Weapon_Description',
       'Victim_Number', 'Domestic_Related', 'Victim_Type',
       'Victim_Description', 'Victim_Gender', 'Victim_Race',
       'Victim_Ethnicity', 'Victim_County_Resident', 'Mapped_Location',
       'POINT_X', 'POINT_Y', 'ZIP_Code', 'Weapon_Primary', 'Incident_Occurred',
       'Incident_Reported']"""
print(schools.columns)


plt.scatter(schools.Longitude, schools.Latitude, c='darkgreen', marker='p')
"""
plt.xlabel('Longitude')
plt.ylabel('Latitude')
plt.title('School Locations')
plt.show()
"""
