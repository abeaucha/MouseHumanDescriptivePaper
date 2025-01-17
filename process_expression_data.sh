#!/bin/bash

# ----------------------------------------------------------------------------
# process_expression_data.sh
# Author: Antoine Beauchamp
#
# Pipeline to process mouse and human gene expression data sets.
#
# Pipeline steps:
# 1. Create a set of atlas labels at multiple levels of granularity using
#    the neuroanatomical trees.
# 2. Create a CSV file containing mouse-human canonical neuroanatomical pairs.
# 3. Intersect mouse and human gene sets with mouse-human gene homologs
#    (in label_expression_matrices.R)
# 4. Label mouse voxel-wise and human sample-wise expression matrices with 
#    neuroanatomical labels at multiple levels in the hierarchy.
# 5. Label mouse sagittal voxel-wise expression matrix for cross-validation
# 6. Label mouse coronal voxel-wise expression matrix with repeated experiments
#    for cross-validation
# 5. Normalize mouse voxel-wise expression matrix.
# 6. Normalize human sample-wise expression matrix.
# 7. Normalize and aggregate mouse expression matrix under 67 atlas labels.
# 8. Normalize and aggregate human expression matrix under 88 atlas labels.

#Create atlas labels
echo "Creating pruned atlas labels from neuroanatomical trees..."
Rscript create_tree_labels.R \
	--outdir data/ \
	--mousetree AMBA/data/MouseExpressionTree_DSURQE.RData \
	--humantree AHBA/data/HumanExpressionTree.RData

#Define canonical neuroanatomical pairs
echo "Define canonical neuroanatomical pairs..."
Rscript create_neuro_pairs.R \
	--outdir data/ \
	--outfile MouseHumanMatches_H88M67.csv

#Label expression matrices
echo "Labelling mouse and human expression matrices..."
Rscript label_expression_matrices.R \
	--mousematrix AMBA/data/MouseExpressionMatrix_voxel_coronal_maskcoronal_log2_grouped_imputed.csv \
	--humanmatrix AHBA/data/HumanExpressionMatrix_samples_pipeline_abagen.csv \
	--mousetree AMBA/data/MouseExpressionTree_DSURQE.RData \
	--humantree AHBA/data/HumanExpressionTree.RData \
	--homologs data/MouseHumanGeneHomologs.csv \
	--outdir data/ \
	--savemouse true \
	--savehuman true
    
echo "Labelling mouse sagittal expression matrix..."
Rscript label_expression_matrices.R \
	--mousematrix AMBA/data/MouseExpressionMatrix_voxel_coronal_masksagittal_log2_imputed.csv \
	--humanmatrix AHBA/data/HumanExpressionMatrix_samples_pipeline_abagen.csv \
	--mousetree AMBA/data/MouseExpressionTree_DSURQE.RData \
	--humantree AHBA/data/HumanExpressionTree.RData \
	--homologs data/MouseHumanGeneHomologs.csv \
	--outdir data/ \
	--savemouse true \
	--savehuman false
    
echo "Labelling mouse coronal expression matrix with repeated experiments..."
Rscript label_expression_matrices.R \
	--mousematrix AMBA/data/MouseExpressionMatrix_voxel_sagittal_masksagittal_log2_grouped_imputed.csv \
	--humanmatrix AHBA/data/HumanExpressionMatrix_samples_pipeline_abagen.csv \
	--mousetree AMBA/data/MouseExpressionTree_DSURQE.RData \
	--humantree AHBA/data/HumanExpressionTree.RData \
	--homologs data/MouseHumanGeneHomologs.csv \
	--outdir data/ \
	--savemouse true \
	--savehuman false

#Normalize and aggregate labelled expression matrices
echo "Processing labelled expression matrices..."

echo "Normalizing mouse voxel expression matrix..."
Rscript process_labelled_matrix.R \
	--infile data/MouseExpressionMatrix_voxel_coronal_maskcoronal_log2_grouped_imputed_labelled.csv \
	--scale true \
	--aggregate false \
	--outdir data/ \
	--verbose true

echo "Normalizing human sample expression matrix..."
Rscript process_labelled_matrix.R \
	--infile data/HumanExpressionMatrix_samples_pipeline_abagen_labelled.csv \
	--scale true \
	--aggregate false \
	--outdir data/ \
	--verbose true

echo "Normalizing and aggregating mouse voxel expression matrix..."
Rscript process_labelled_matrix.R \
	--infile data/MouseExpressionMatrix_voxel_coronal_maskcoronal_log2_grouped_imputed_labelled.csv \
	--scale true \
	--aggregate true \
	--nlabels 67 \
	--outdir data/ \
	--verbose true

echo "Normalizing and aggregating human sample expression matrix..."
Rscript process_labelled_matrix.R \
	--infile data/HumanExpressionMatrix_samples_pipeline_abagen_labelled.csv \
	--scale true \
	--aggregate true \
	--nlabels 88 \
	--outdir data/ \
	--verbose true
