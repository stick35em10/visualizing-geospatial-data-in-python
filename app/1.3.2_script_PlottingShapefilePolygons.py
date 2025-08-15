
# Import packages
import geopandas as gpd
from path import service_district #, world, maputo_, roads, hospitais  # Import the necessary paths
import matplotlib.pyplot as plt

# Plot the Service Districts without any additional arguments
#service_district.plot()
#plt.show()
print(service_district.columns)
print(service_district.head())
# Plot the Service Districts, color them according to name, and show a legend
service_district.plot(column = 'name', legend = True)
#plt.show()
#file_naimg/1_Building_2_Layer_Maps/1.3.1_Geometry/_2.PlottingShapefil
#ePpolygons.png
img_file_name = "img/1_Building_2_Layer_Maps/1.3.1_Geometry/_2.PlottingShapefilePpolygons.png"
plt.savefig(img_file_name_)