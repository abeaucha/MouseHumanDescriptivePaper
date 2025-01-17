
#On MICe machines: Remove all modules
module purge

#If venv does not exist, create it
if [ ! -d ".venv" ]; then
	echo "Initializing python virtual environment..."

	#Create the venv
	python3 -m venv .venv

	echo "Installing python packages..."

	#Activate the venv
	source .venv/bin/activate

	#Upgrade pip
	echo "Upgrading pip..."
	pip install pip --upgrade

	#Install necessary python packages
	pip3 install -r python_reqs.txt

	#Deactivate the venv
	deactivate
fi

#Load necessary modules 
#NOTE: minc-stuffs module break python virtual environment
#module load minc-toolkit/1.9.18.1-mp7vcse minc-stuffs/0.1.25-4jzbv5d r/3.6.3-zlk4uk6 r-packages/2022-01-26
module load minc-toolkit/1.9.18.1-mp7vcse r/3.6.3-zlk4uk6 r-packages/2022-01-26

#Activate the python venv
source .venv/bin/activate
