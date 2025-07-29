# Load the data
#C:\Users\Admin\Downloads\Metro_Nashville_Police_Department_Incidents.csv
#schools = pd.read_csv('https://data.nashville.gov/Education/Metro-Nashville-Public-Schools-School-Directory/7qhq-4vgb')  # Make sure this file exists and has Longitude/Latitude columns

path_file = 'data/Metro_Nashville_Police_Department_Incidents.csv'
chickens_path = 'https://assets.datacamp.com/production/repositories/2409/datasets/fa767727ef9a7b39fb9f34bee3b1bc2f02682c81/Domesticated_Hen_Permits_clean_adjusted_lat_lng.csv'

# Update the path to where you unzipped the shapefile
#shapefile_path = "data/ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp"
shapefile_path = "data/maps/ne_110m_admin_0_countries.shp"
