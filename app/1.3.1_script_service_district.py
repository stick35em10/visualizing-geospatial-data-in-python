# Import geopandas
import geopandas as gpd

#https://campus.datacamp.com/courses/visualizing-geospatial-data-in-python/building-2-layer-maps-combining-polygons-and-scatterplots?ex=7
# Creating a GeoDataFrame & examining the geometry
shapefile_path = "data/Service District/geo_export_ca87c034-2403-454e-8057-a3776934ed64.shp"
#geo_export_ca87c034-2403-454e-8057-a3776934ed64.shp
#print(shapefile_path)

# Read in the services district shapefile and look at the first few rows.
service_district = gpd.read_file(shapefile_path)
print(service_district.head())

# Print the contents of the service districts geometry in the first row
print(service_district.loc[0, 'geometry'])