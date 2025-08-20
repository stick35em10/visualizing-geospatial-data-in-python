# Usa uma imagem base Python leve
FROM python:3.9-slim

# Define o diretório de trabalho no contêiner
WORKDIR /app

# Copia o arquivo de dependências primeiro para aproveitar o cache do Docker
COPY requirements_for_render.txt requirements.txt

# Instala as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código da aplicação para o contêiner
COPY . .

#Run ls /app #- ConsistentInstructionCasing: Command 'Run' should match the case of the command majority (uppercase) (line 16)
# Expõe a porta que o Flask vai usar (5000 por padrão)
EXPOSE 5000

# Comando para iniciar a aplicação
# Usa Gunicorn ou Waitress para produção. Para este exemplo, o Flask é suficiente.
#CMD ["flask", "run app/19.08/19.08_04:43_script_foto_mapa_", "--host=0.0.0.0"]
#CMD ["flask", "--app", "app.app/19.08/19.08_04:43_script_foto_mapa_", "run", "--host=0.0.0.0"]
CMD ["flask", "run", "--host=0.0.0.0"]
# docker rmi your-image-name:05 && docker build -t your-image-name:06 .
# git add 
# 

#git pull origin 01_03_01_Plotting_points_over_polygons_part_2_01       
#git add Dockerfile .gitignore .vincent/ app.py 
#git commit -m "git add Dockerfile .gitignore .vincent/ app.py "
#git push --set-upstream origin 01_03_01_Plotting_points_over_polygons_part_2_01
# docker rmi your-image-name && docker build -t your-image-name . && docker run -p 5000:5000 your-image-name