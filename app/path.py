import geopandas as gpd
# Load the data
#C:\Users\Admin\Downloads\Metro_Nashville_Police_Department_Incidents.csv
#schools = pd.read_csv('https://data.nashville.gov/Education/Metro-Nashville-Public-Schools-School-Directory/7qhq-4vgb')  # Make sure this file exists and has Longitude/Latitude columns

path_file = 'data/Metro_Nashville_Police_Department_Incidents.csv'

chickens_path = 'https://assets.datacamp.com/production/repositories/2409/datasets/fa767727ef9a7b39fb9f34bee3b1bc2f02682c81/Domesticated_Hen_Permits_clean_adjusted_lat_lng.csv'
chickens = gpd.read_file(chickens_path) 
# Update the path to where you unzipped the shapefile
#shapefile_path = "data/ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp"
shapefile_path = "data/maps/ne_110m_admin_0_countries.shp"
service_district = gpd.read_file(shapefile_path)
#import geopandas as gpd
#gadm41_MOZ_3.shp
#maputo = gpd.read_file("data/maps/maputo_admin.shp")
#maputo = gpd.read_file("data/maps/gadm41_MOZ_3.shp")
maputo_path = "data/maps/gadm41_MOZ_3.shp"

maputo_ = gpd.read_file(maputo_path)
#maputo_path = "data/maps/gadm41_MOZ_3.shp"

#data/maps/ne_110m_admin_0_countries.shp
#maputo = gpd.read_file("data/maps/ne_110m_admin_0_countries.shp")
#inflating: data/maps/gadm41_MOZ_0.shp
#  inflating: data/maps/gadm41_MOZ_1.shp
# inflating: data/maps/gadm41_MOZ_2.shp
# inflating: data/maps/gadm41_MOZ_3.shp 
# Limite de Maputo

# Vias de acesso
roads_path_ = "data/maps/gis_osm_roads_free_1.shp"

# Hospitais em Maputo
#hospitais = gpd.read_file("data/maps/hospitais_maputo.shp")
# gadm41_MOZ_1.shp, gadm41_MOZ_2.shp, gadm41_MOZ_3.shp, ne_110m_admin_1_states_provinces.shp
#pyogrio.errors.DataSourceError: data/maps/hospitais_maputo.shp: No such file or directory


#roads = gpd.read_file("data/maps/gis_osm_roads_free_1.shp")


#hospitais = gpd.read_file("data/maps/gadm41_MOZ_0.shp") #gadm41_MOZ_1.shp, gadm41_MOZ_2.shp, gadm41_MOZ_3.shp, ne_110m_admin_1_states_provinces.shp, 

hospitais_path = "data/maps/gadm41_MOZ_0.shp" #gpd.read_file("data/maps/gadm41_MOZ_0.shp") #gadm41_MOZ_1.shp, gadm41_MOZ_2.shp, gadm41_MOZ_3.shp, ne_110m_admin_1_states_provinces.shp, 


#inflating: data/maps/gis_osm_buildings_a_free_1.shp, inflating: data/maps/gis_osm_landuse_a_free_1.shp, data/maps/gis_osm_natural_a_free_1.shp , data/maps/gis_osm_natural_free_1.shp, 
# data/maps/gis_osm_places_a_free_1.shp, data/maps/gis_osm_places_free_1.shp, data/maps/gis_osm_pofw_a_free_1.shp , data/maps/gis_osm_pofw_free_1.shp, data/maps/gis_osm_pois_a_free_1.shp
# data/maps/gis_osm_pois_free_1.shp, data/maps/gis_osm_railways_free_1.shp, data/maps/gis_osm_roads_free_1.shp, data/maps/gis_osm_traffic_a_free_1.shp
# data/maps/gis_osm_traffic_free_1.shp, data/maps/gis_osm_transport_a_free_1.shp, data/maps/gis_osm_transport_free_1.shp , 
# data/maps/gis_osm_water_a_free_1.shp, data/maps/gis_osm_waterways_free_1.shp
