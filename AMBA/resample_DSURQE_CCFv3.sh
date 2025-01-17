#!/bin/bash
# -----------------------------------------------------------------------------
# resample_DSURQE_CCFv3
#
# Resample imaging files from the DSURQE common coordinate space to the 
# Allen Institute CCFv3 space.

module purge
module load minc-toolkit/1.9.18.1-mp7vcse minc-stuffs/0.1.25-4jzbv5d

echo "Resampling DSURQE consensus average template to Allen CCFv3 space..."

mincresample -like data/imaging/average_template_200um.mnc -transform data/imaging/MICe_DSURQE.xfm data/imaging/DSURQE_40micron_average.mnc data/imaging/DSURQE_CCFv3_average_200um.mnc -clobber

mincresample -like data/imaging/average_template_50um.mnc -transform data/imaging/MICe_DSURQE.xfm data/imaging/DSURQE_40micron_average.mnc data/imaging/DSURQE_CCFv3_average_50um.mnc -clobber

echo "Resampling DSURQE atlas labels to Allen CCFv3 space..."

#Note that running mincresample with the -label flag generates non-existent false labels.
#Better to use -nearest and then minc_label_ops
mincresample -like data/imaging/average_template_200um.mnc -transform data/imaging/MICe_DSURQE.xfm data/imaging/DSURQE_40micron_labels.mnc data/imaging/DSURQE_CCFv3_nearest_200um.mnc -nearest -clobber

minc_label_ops --convert data/imaging/DSURQE_CCFv3_nearest_200um.mnc data/imaging/DSURQE_CCFv3_labels_200um.mnc

rm data/imaging/DSURQE_CCFv3_nearest_200um.mnc

echo "Resampling DSURQE mask to Allen CCFv3 space..."
mincresample \
	-like data/imaging/average_template_200um.mnc \
	-transform data/imaging/MICe_DSURQE.xfm \
	data/imaging/DSURQE_40micron_mask.mnc \
	data/imaging/DSURQE_CCFv3_mask_200um_tmp.mnc \
	-nearest \
	-clobber

minc_label_ops --convert \
	data/imaging/DSURQE_CCFv3_mask_200um_tmp.mnc \
	data/imaging/DSURQE_CCFv3_mask_200um.mnc 


rm data/imaging/DSURQE_CCFv3_mask_200um_tmp.mnc

module purge
