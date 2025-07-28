import pandas as pd
import matplotlib.pyplot as plt
import os

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

## Scatterplot 1 - father heights vs. son heights with darkred square markers
# como usar um helper para plotar scatterplot
# Create a scatterplot of father and son heights with a square marker (encoded as s)
#

def create_scatterplot(x, y, color='darkred', marker='s', xlabel='X-axis', ylabel='Y-axis', title='Scatterplot', file_name=f"img/Longitude_Latitude_school_locations_s.png"):
    plt.scatter(x, y, c=color, marker=marker)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid()
    run_date = os.getenv("RUN_DATE", "local")
    run_number = os.getenv("RUN_NUMBER", "0")
    img_name = f"img/school_locations_{run_date}_run{run_number}.png"
    plt.savefig(img_name)
    #plt.show()
    #plt.savefig(file_name)  # Save the plot as a PNG image
    #filename='img/school_locations_s.png'
    #file_name = file_name if f"img/{x}_{y}_{title}_s.png" else filename

create_scatterplot(schools.Longitude, schools.Latitude, color='darkred', marker='s', xlabel='Longitude', ylabel='Latitude', title='School Locations', file_name=f"img/Longitude_Latitude_school_locations_s.png")
# Create_scatterplot of school locations with a pentagon marker (encoded as 'p') that is 'darkgreen'.
#plt.scatter(schools.Longitude, schools.Latitude, c='darkgreen', marker='s') #'p')

#plt.xlabel('Longitude')
#plt.ylabel('Latitude')
#plt.title('School Locations')
#plt.savefig("img/school_locations_s.png")  # Save the plot as a PNG image
#plt.show() # Show your plot

#Create a scatterplot of father and son heights with a square marker (encoded as s) that is 'darkred'. Show your plot.
#plt.scatter(schools.Longitude, schools.Latitude, c='darkgreen', marker='s') #'p')

# plt.scatter(father_son.fheight, father_son.sheight, ____ = 'darkred', ____ = 's')
# NameError: name 'father_son' is not defined
# plt.scatter(father_son.fheight, father_son.sheight, c = 'darkred', marker= 's')
# plt.xlabel('Father Height (inches)')
# plt.ylabel('Son Height (inches)')
# plt.title('Father vs Son Heights')
# plt.xlabel('Longitude')
# plt.ylabel('Latitude')
# plt.title('School Locations')
#plt.show()
# plt.savefig("img/scatter_school_locations_s.png")  # Save the plot as a PNG image


