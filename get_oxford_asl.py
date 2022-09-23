import os 
import subprocess
import sys
import glob
import json
import numpy as np 
import pydicom as dcm
import nibabel as nib 

#### MAIN METHOD PURPOSE ####
# takes single ASL study dir after dcm2niix as input
# assumes BIDS metadata present and fsl_anat already ran
# reads metadata (& DICOM headers?) for ASL image in study
# then auto-populates parameters for oxford_asl call

'''def prep_data(study):
	# load data
	assert os.path.isdir(study)
	os.chdir(study)
	jsons = glob.glob('*.json')
	anat = glob.glob('*.anat')[0]
	asls = []
	mocos = []
	for j in jsons:
		if 'PASL' in j or '_real' in j:
			asls.append(j)
			if '_MoCo_' in j:
				mocos.append(j)
	# assign data as temp to get manufacturer info		
	data = json.load(open(asls[0]))	
	return'''

# runs fsl_anat to process T1 image
'''def run_anat(study):
	os.system('fsl_anat -i ' + t1_img)
	return'''

def get_oxford_asl(study):
	# load data
	assert os.path.isdir(study)
	os.chdir(study)
	jsons = glob.glob('*.json')
	anat = glob.glob('*.anat')[0]
	asls = []
	mocos = []
	for j in jsons:
		if 'PASL' in j or '_real' in j:
			asls.append(j)
			# applies to Siemens acquisition only
			if '_MoCo_' in j:
				mocos.append(j)
	# assign data as temp to get manufacturer info		
	data = json.load(open(asls[0]))		
	# parse metadata to get parameters
	if data['Manufacturer'] == 'Siemens':
		# Siemens is always PASL
		# make sure data is original ASL image
		if len(mocos) == 0:
			if 'ORIGINAL' in data['ImageType']:
				filename = asls[0]
			else:
				for a in asls:
					d = json.load(open(a))
					if 'ORIGINAL' in d['ImageType']:
						data = d
						filename = a
						break
		else:
			for m in mocos:
				d = json.load(open(m))
				if d['SeriesDescription'] != 'Perfusion_Weighted' and d['SeriesDescription'] != 'relCBF':
					data = d
					filename = m
					break			
		iaf = 'ct' 
		tis = str(data['InversionTime'])
		bolus = str(data['BolusDuration'])
		fslanat = anat
		oxford_asl_call = 'oxford_asl -i ' + filename.replace('.json','.nii') + ' -o . --iaf=' + iaf + ' --tis=' + tis + ' --bolus=' + bolus + ' --fslanat=' + anat	
		# get fieldmaps if are present and add to oxford_asl_call
		fieldmaps = []
		for j in jsons:
			if 'Field_Mapping' in j:
				fieldmaps.append(j)
		if len(fieldmaps) != 0:
			calculated_fieldmap, echospacing, pedir = get_fieldmap(fieldmaps)
			oxford_asl_call = oxford_asl_call + ' --fmap=' + calculated_fieldmap + ' --echospacing=' + echospacing + ' --pedir=' + pedir
		if data['MRAcquisitionType'] == '2D':
			slice_times = data['SliceTiming']
			slicedt = str(slice_times[1] - slice_times[0])
			oxford_asl_call = oxford_asl_call + ' --slicedt=' + slicedt
			# get M0 image from first volume of data if it exists
			img = nib.load(filename.replace('.json','.nii'))
			img_data = img.get_fdata()
			if img_data.shape[3] % 2 == 1:
				m0 = img_data[:,:,:,0]
				m0 = nib.Nifti1Image(m0,img.affine,img.header)
				nib.save(m0,'m0.nii')
				tr = str(data['RepetitionTime'])
				oxford_asl_call = oxford_asl_call + ' -c m0.nii --tr=' + tr 
		elif data['MRAcquisitionType'] == '3D':
			# oxford_asl defaults to 3D if no slice timing present
			pass	
	elif data['Manufacturer'] == 'GE':
		# GE is always 3D pCASL
		# make sure data is derived ASL image and calibration is original
		if 'DERIVED' in data['ImageType'] and 'CBF' not in data['ImageType']:
			filename = asls[0]
		else:
			for a in asls:
				d = json.load(open(a))
				if 'DERIVED' in d['ImageType'] and 'CBF' not in d['ImageType']:	
					data = d
					filename = a
					break
		iaf = 'diff'
		tis = str(data['LabelingDuration'] + data['PostLabelingDelay'])
		bolus = str(data['LabelingDuration'])
		oxford_asl_call = 'oxford_asl -i ' + filename.replace('.json','.nii') + ' -o . --casl --iaf=' + iaf + ' --tis=' + tis + ' --bolus=' + bolus + ' --fslanat=' + anat	
		# calibration parameters
		calib = 0
		for a in asls:
			d = json.load(open(a))
			if 'ORIGINAL' in d['ImageType']:
				calib = d
				calib_filename = a
				break
		if calib:
			tr = str(calib['RepetitionTime'])
			oxford_asl_call = oxford_asl_call + ' -c ' + calib_filename.replace('.json','.nii') + ' --tr=' + tr
	elif data['Manufacturer'] == 'Philips':
		# Philips is always 2D PASL
		if 'ORIGINAL' in data['ImageType']:
				filename = asls[0]
			else:
				for a in asls:
					d = json.load(open(a))
					if 'ORIGINAL' in d['ImageType']:
						data = d
						filename = a
						break
		iaf = 'tc'
		slicedt = input('enter estimate for slice timing: ')
		# get parameters from user when they are not present
		# get fieldmaps if they are present and add to oxford_asl_call
	# outputs call to oxford_asl
	print('oxford_asl call:')
	print(oxford_asl_call)
	return oxford_asl_call	

# prepares the fieldmap for use with Siemens PASL data
def get_fieldmap(fieldmaps):
	# run BET on magnitude image
	for f in fieldmaps:
		if '_e2' in f and '_ph' not in f:
			os.system('bet '+f.replace('.json','.nii')+' '+f.replace('.json','_be.nii'))
			fieldmap_mag_be = f.replace('.json','_be.nii.gz')
		elif '_e2_ph' in f:
			fieldmap_phase_filename = json.load(open(f))
			fieldmap_phase = f.replace('.json','.nii')	
	# run fsl_prepare_fieldmap
	os.system('fsl_prepare_fieldmap SIEMENS '+fieldmap_phase+' '+fieldmap_mag_be+' calculated_fieldmap.nii 2.46')
	# output calculated_fieldmap and fieldmap parameters
	calculated_fieldmap = 'calculated_fieldmap.nii.gz'
	echospacing = str(fieldmap_phase_filename['DwellTime'])
	if fieldmap_phase_filename['PhaseEncodingDirection'] == 'i':
		pedir = 'x'
	elif fieldmap_phase_filename['PhaseEncodingDirection'] == 'i-':
		pedir = '-x'
	elif fieldmap_phase_filename['PhaseEncodingDirection'] == 'j':
		pedir = 'y'
	elif fieldmap_phase_filename['PhaseEncodingDirection'] == 'j-':
		pedir = '-y'
	elif fieldmap_phase_filename['PhaseEncodingDirection'] == 'k':
		pedir = 'z'
	elif fieldmap_phase_filename['PhaseEncodingDirection'] == 'k-':
		pedir = '-z'		
	print('prepared fieldmap for use with oxford_asl')
	return calculated_fieldmap, echospacing, pedir

# runs oxford_asl from the command line
'''def run_asl(oxford_asl_call):
	os.system(oxford_asl_call)
	return'''

if __name__=='__main__':
	get_oxford_asl(sys.argv[1])
