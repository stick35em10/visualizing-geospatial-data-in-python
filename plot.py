import pandas as pd
import matplotlib.pyplot as plt
import os
import geopandas as gpd

# Load the data
#C:\Users\Admin\Downloads\Metro_Nashville_Police_Department_Incidents.csv
#schools = pd.read_csv('https://data.nashville.gov/Education/Metro-Nashville-Public-Schools-School-Directory/7qhq-4vgb')  # Make sure this file exists and has Longitude/Latitude columns

path_file = 'data/Metro_Nashville_Police_Department_Incidents.csv'
chickens_path = 'https://assets.datacamp.com/production/repositories/2409/datasets/fa767727ef9a7b39fb9f34bee3b1bc2f02682c81/Domesticated_Hen_Permits_clean_adjusted_lat_lng.csv'

schools = pd.read_csv(path_file)  # Make sure this file exists and has Longitude/Latitude columns
chickens = pd.read_csv(chickens_path)

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

# print the first few rows of df 
print(schools.head())

# extract latitude to a new column: lat
#df['lat'] = [loc[0] for loc in df.Location]

# extract longitude to a new column: lng
#df['lng'] = [loc[1] for loc in df.Location]

# print the first few rows of df again
#print(df.head())

#plt.xlabel('Longitude')
#plt.ylabel('Latitude')
#plt.title('School Locations')
#plt.savefig("img/school_locations_s.png")  # Save the plot as a PNG image
#plt.show() # Show your plot

# Look at the first few rows of the chickens DataFrame
print(chickens.head())

# Plot the locations of all Nashville chicken permits
#plt.scatter(x = chickens.lat, y = chickens.lng)

#create_scatterplot(schools.Longitude, schools.Latitude, color='darkred', marker='s', xlabel='Longitude', ylabel='Latitude', title='School Locations', file_name=f"img/Longitude_Latitude_school_locations_s.png")
create_scatterplot(chickens.lng, chickens.lat,  color='darkred', marker='p', xlabel='Longitude', ylabel='Latitude', title='Chicken Locations', file_name=f"img/Chicken_Locations.png")

# Show the plot
#plt.show()
print(" import geopandas")
import geopandas as gpd
import matplotlib.pyplot as plt

print("world = gpd.read_file(gpd.datasets.get_path(")
# Load the world map

# Update the path to where you unzipped the shapefile
#shapefile_path = "data/ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp"
shapefile_path = "data/maps/ne_110m_admin_0_countries.shp"
world = gpd.read_file(shapefile_path)
mozambique = world[world['ADMIN'] == 'Mozambique']
print("mozambique = world[world['admin'] == 'Mozambique']")
print("mozambique = world[world.admin ==")
# Plot
mozambique.plot(edgecolor='black', color='lightblue')
plt.title("Mozambique - Geometry Map")
#plt.show()

plt.savefig("img/1_Building_2_Layer_Maps/Mozambique_Geometry_Map.png")  # Save the plot as a PNG image
print("plt.savefig(")
#plt.show() # Show your plot

# https://campus.datacamp.com/courses/visualizing-geospatial-data-in-python/building-2-layer-maps-combining-polygons-and-scatterplots?ex=7
#1.2.1 Creating a GeoDataFrame & examining the geometry
# Import geopandas
#import geopandas as gpd

print(shapefile_path)

# Read in the services district shapefile and look at the first few rows.
service_district = gpd.read_file(shapefile_path)
print(service_district.head())

# Print the contents of the service districts geometry in the first row
print(service_district.loc[0, 'geometry'])

service_district.plot(edgecolor='black', color='lightblue')
#AttributeError: 'GeoDataFrame' object has no attribute 'title'
#Error: Process completed with exit code 1.
ax = service_district.plot(edgecolor='black', color='lightblue')
plt.title("Mozambique - Geometry Map")  # Defina o título
plt.savefig("img/1_Building_2_Layer_Maps/2._1_service_district_Building_2_Layer_Maps_Mozambique_Geometry_Map.png")
plt.close()  # Fecha a figura para liberar memória (opcional)
