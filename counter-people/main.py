# import the necessary packages
import numpy as np
import argparse
import imutils
from imutils.video import FPS
import time
import cv2
import os
from datetime import datetime
import csv

from sort import *
tracker = Sort()
memory = {}
#line = [(43, 543), (550, 655)]
#line = [((W // 2) + 350, (H // 2)), ((W // 2) + 130, H - 200)]
counter = 0

#if os.stat('count_pedestrians_{}.csv'.format(datetime.today().strftime('%d-%m-%y'))).st_size == 0:

a = "count_pedestrians_{}.csv'.format(datetime.today().strftime('%d-%m-%y')) "
#with open('count_pedestrians_03-07-22.csv', 'r+', encoding='UTF8') as f:
	#readcsv = csv.reader(f)
	#writercsv = csv.writer(readcsv)
	#writercsv.writerow(["Data", "Horário", "Número de pedestres"])

# construct the argument parse and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-i", "--input", type=str,
	help="path to input video")
ap.add_argument("-o", "--output", required=True,
	help="path to output video")
ap.add_argument("-y", "--yolo", required=True,
	help="base path to YOLO directory")
ap.add_argument("-c", "--confidence", type=float, default=0.5,
	help="minimum probability to filter weak detections")
ap.add_argument("-t", "--threshold", type=float, default=0.3,
	help="threshold when applyong non-maxima suppression")
ap.add_argument("-u", "--gpu", type=bool, default=0, help="boolean indicating if CUDA GPU should be used")
args = vars(ap.parse_args())

# Return true if line segments AB and CD intersect
def intersect(A,B,C,D):
	return ccw(A,C,D) != ccw(B,C,D) and ccw(A,B,C) != ccw(A,B,D)

def ccw(A,B,C):
	return (C[1]-A[1]) * (B[0]-A[0]) > (B[1]-A[1]) * (C[0]-A[0])

# load the COCO class labels our YOLO model was trained on
labelsPath = os.path.sep.join([args["yolo"], "coco.names"])
LABELS = open(labelsPath).read().strip().split("\n")

# initialize a list of colors to represent each possible class label
np.random.seed(42)
COLORS = np.random.randint(0, 255, size=(200, 3),
	dtype="uint8")

# derive the paths to the YOLO weights and model configuration
weightsPath = os.path.sep.join([args["yolo"], "yolov4-tiny-obj_best.weights"])
configPath = os.path.sep.join([args["yolo"], "yolov4-tiny-obj.cfg"])

# load our YOLO object detector trained on COCO dataset (80 classes)
# and determine only the *output* layer names that we need from YOLO
print("[INFO] loading YOLO from disk...")
net = cv2.dnn.readNetFromDarknet(configPath, weightsPath)

if args["gpu"]:
	net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
	net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)

ln = net.getLayerNames()
ln = [ln[i - 1] for i in net.getUnconnectedOutLayers()]

# initialize the video stream, pointer to output video file, and
# frame dimensions
if not args.get("input", False):
	print("[INFO] starting video stream...")
	url = "https://5b33b873179a2.streamlock.net:1443/camerafozaduana/camerafozaduana.stream/chunklist_w1529507329.m3u8"
	vs = cv2.VideoCapture(url)
# otherwise, grab a reference to the video file
else:
	print("[INFO] opening video file...")
	vs = cv2.VideoCapture(args["input"])
#vs = cv2.VideoCapture(args["input"])
writer = None
(W, H) = (1920, 1080)

if not args.get("input", False):
	#tempo real
	centerline = [((W // 2) + 200, (H // 2)), ((W // 2) + 25, H - 300)]
	centerline2 = [((W // 2), H - 200 ), ((W // 2) - 50, H )]
	#leftline = [((W // 2) - 150, H - 300), ((W // 2) - 600, H )]
	rightline = [((W // 2) + 560, (H // 2) + 200), ((W // 2) + 560, H)]
else:
    centerline = [((W // 2) + 300, (H // 2)), ((W // 2) + 75, H - 200)]
    centerline2 = [((W // 2) - 15, H - 120 ), ((W // 2) - 100, H )]
    #leftline = [((W // 2) - 50, H - 300), ((W // 2) - 500, H )]
    rightline = [((W // 2) + 660, (H // 2) + 270), ((W // 2) + 660, H)]	

fps = FPS().start()

frameIndex = 0

# try to determine the total number of frames in the video file
try:
	prop = cv2.cv.CV_CAP_PROP_FRAME_COUNT if imutils.is_cv2() \
		else cv2.CAP_PROP_FRAME_COUNT
	total = int(vs.get(prop))
	print("[INFO] {} total frames in video".format(total))

# an error occurred while trying to determine the total
# number of frames in the video file
except:
	print("[INFO] could not determine # of frames in video")
	print("[INFO] no approx. completion time can be provided")
	total = -1

num_frames = 0
while True:
	# read the next frame from the file
	(grabbed, frame) = vs.read()

	# if the frame was not grabbed, then we have reached the end
	# of the stream
	if not grabbed:
		break

	print("================NEW FRAME================")
	num_frames += 1
	print("FRAME:\t", num_frames)
	# if the frame dimensions are empty, grab them
	if W is None or H is None:
		(H, W) = frame.shape[:2]

	# construct a blob from the input frame and then perform a forward
	# pass of the YOLO object detector, giving us our bounding boxes
	# and associated probabilities
	blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, (416, 416),
		swapRB=True, crop=False)
	net.setInput(blob)
	start = time.time()
	layerOutputs = net.forward(ln)
	end = time.time()

	# initialize our lists of detected bounding boxes, confidences,
	# and class IDs, respectively
	boxes = []
	confidences = []
	classIDs = []

	# loop over each of the layer outputs
	for output in layerOutputs:
		# loop over each of the detections
		for detection in output:
			# extract the class ID and confidence (i.e., probability)
			# of the current object detection
			scores = detection[5:]
			classID = np.argmax(scores)
			confidence = scores[classID]

			# filter out weak predictions by ensuring the detected
			# probability is greater than the minimum probability
			if confidence > args["confidence"]:
				# scale the bounding box coordinates back relative to
				# the size of the image, keeping in mind that YOLO
				# actually returns the center (x, y)-coordinates of
				# the bounding box followed by the boxes' width and
				# height
				box = detection[0:4] * np.array([W, H, W, H])
				(centerX, centerY, width, height) = box.astype("int")

				# use the center (x, y)-coordinates to derive the top
				# and and left corner of the bounding box
				x = int(centerX - (width / 2))
				y = int(centerY - (height / 2))

				# update our list of bounding box coordinates,
				# confidences, and class IDs
				boxes.append([x, y, int(width), int(height)])
				confidences.append(float(confidence))
				classIDs.append(classID)

	# apply non-maxima suppression to suppress weak, overlapping
	# bounding boxes
	idxs = cv2.dnn.NMSBoxes(boxes, confidences, args["confidence"], args["threshold"])
	
	dets = []
	if len(idxs) > 0:
		# loop over the indexes we are keeping
		for i in idxs.flatten():
			(x, y) = (boxes[i][0], boxes[i][1])
			(w, h) = (boxes[i][2], boxes[i][3])
			dets.append([x, y, x+w, y+h, confidences[i]])

		np.set_printoptions(formatter={'float': lambda x: "{0:0.3f}".format(x)})
		dets = np.asarray(dets)
		tracks = tracker.update(dets)

		boxes = []
		indexIDs = []
		c = []
		previous = memory.copy()
		memory = {}

		for track in tracks:
			boxes.append([track[0], track[1], track[2], track[3]])
			indexIDs.append(int(track[4]))
			memory[indexIDs[-1]] = boxes[-1]

		if len(boxes) > 0:
			i = int(0)
			for box in boxes:
			# extract the bounding box coordinates
				(x, y) = (int(box[0]), int(box[1]))
				(w, h) = (int(box[2]), int(box[3]))

			# draw a bounding box rectangle and label on the image
			# color = [int(c) for c in COLORS[classIDs[i]]]
			# cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

			#color = [int(c) for c in COLORS[indexIDs[i] % len(COLORS)]]
				cv2.rectangle(frame, (x, y), (w, h), (255,0,0), 2)
				pedestrian = 0
				if indexIDs[i] in previous:
					previous_box = previous[indexIDs[i]]
					(x2, y2) = (int(previous_box[0]), int(previous_box[1]))
					(w2, h2) = (int(previous_box[2]), int(previous_box[3]))
					p0 = (int(x + (w-x)/2), int(y + (h-y)/2))
					p1 = (int(x2 + (w2-x2)/2), int(y2 + (h2-y2)/2))
					cv2.line(frame, p0, p1, (255,255,0), 3)

					if intersect(p0, p1, centerline[0], centerline[1]):
						counter += 1
						print("pedestre :\t", counter)
						cv2.imwrite("output/frame_{}_{}.png".format(frameIndex, datetime.today().strftime('%d-%m-%y')), frame)
						#with open('count_pedestrians_{}.csv'.format(datetime.today().strftime('%d-%m-%y')), 'a+', encoding='UTF8') as f:
						#	writercsv = csv.writer(f)
						#	writercsv.writerow(["{}".format(datetime.today().strftime('%d-%m-%y')), 
                        #   "{}".format(datetime.today().strftime('%H:%M:%S')), "1"])
       
					#elif intersect(p0, p1, leftline[0], leftline[1]):
						#counter += 1
						#print("pedestre :\t", counter)
						#cv2.imwrite("output/frame_{}_{}.png".format(frameIndex, datetime.today().strftime('%d-%m-%y')), frame)
						#with open('count_pedestrians_{}.csv'.format(datetime.today().strftime('%d-%m-%y')), 'a+', encoding='UTF8') as f:
						#	writercsv = csv.writer(f)
						#	writercsv.writerow(["{}".format(datetime.today().strftime('%d-%m-%y')), 
                        #   "{}".format(datetime.today().strftime('%H:%M:%S')), "1"])
			
					elif intersect(p0, p1, rightline[0], rightline[1]):
						counter += 1
						print("pedestre :\t", counter)
						cv2.imwrite("output/frame_{}_{}.png".format(frameIndex, datetime.today().strftime('%d-%m-%y')), frame)
						#with open('count_pedestrians_{}.csv'.format(datetime.today().strftime('%d-%m-%y')), 'a+', encoding='UTF8') as f:
						#	writercsv = csv.writer(f)
						#	writercsv.writerow(["{}".format(datetime.today().strftime('%d-%m-%y')), 
                        #   "{}".format(datetime.today().strftime('%H:%M:%S')), "1"])

					elif intersect(p0, p1, centerline2[0], centerline2[1]):
						counter += 1
						print("pedestre :\t", counter)
						cv2.imwrite("output/frame_{}_{}.png".format(frameIndex, datetime.today().strftime('%d-%m-%y')), frame)
						#with open('count_pedestrians_{}.csv'.format(datetime.today().strftime('%d-%m-%y')), 'a+', encoding='UTF8') as f:
						#	writercsv = csv.writer(f)
						#	writercsv.writerow(["{}".format(datetime.today().strftime('%d-%m-%y')), 
                         #  "{}".format(datetime.today().strftime('%H:%M:%S')), "1"])
					
				text = "{},{}-{:.4f}".format(indexIDs[i],LABELS[classIDs[i]], confidences[i])
				#text = "{}".format(indexIDs[i])
				cv2.putText(frame, text, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)
				i += 1
     
    #linha do meio
	cv2.line(frame, centerline[0], centerline[1], (0, 255, 255), 2)
    #linha da direita
	cv2.line(frame, rightline[0], rightline[1], (0, 255, 255), 2)
    #linha do meio pequena
	cv2.line(frame, centerline2[0], centerline2[1], (0, 255, 255), 2)
    #linha da esquerda
	#cv2.line(frame, leftline[0], leftline[1], (0, 255, 255), 2)

	# draw counter
	cv2.putText(frame, str(counter), (100,200), cv2.FONT_HERSHEY_DUPLEX, 5.0, (0, 255, 255), 10)
	# counter += 1

	# saves image file
	#cv2.imwrite("output/frame-{}.png".format(frameIndex), frame)
	if not args.get("input", False):
		#frame = frame[0: (H //2)+400, 100:W - 120]
		frame = cv2.resize(frame, (0, 0), fx=0.8, fy=0.8)
	else:
		frame = cv2.resize(frame, (0, 0), fx=0.8, fy=0.8)

	cv2.imshow("Frame", frame)
	key = cv2.waitKey(1) & 0xFF
	# if the `q` key was pressed, break from the loop
	if key == ord("q"):
		break

	# check if the video writer is None
	if writer is None:
		# initialize our video writer
		fourcc = cv2.VideoWriter_fourcc(*"MJPG")
		writer = cv2.VideoWriter(args["output"], fourcc, 30,
			(frame.shape[1], frame.shape[0]), True)

		# some information on processing single frame
		if total > 0:
			elap = (end - start)
			print("[INFO] single frame took {:.4f} seconds".format(elap))
			print("[INFO] estimated total time to finish: {:.4f}".format(
				elap * total))

	# write the output frame to disk
	writer.write(frame)
	fps.update()

	# increase frame index
	frameIndex += 1

	if frameIndex >= 1000:
		print("[INFO] cleaning up...")
		fps.stop()
		print("[INFO] approx. FPS: {:.2f}".format(fps.fps()))
		writer.release()
		vs.release()
		exit()

#with open('count_pedestrians_{}.csv'.format(datetime.today().strftime('%d-%m-%y')), 'a+', encoding='UTF8') as f:
	#writercsv = csv.writer(f)
	#writercsv.writerow(["Total de pedestres", "{}".format(counter)])

# release the file pointers
fps.stop()
print("[INFO] approx. FPS: {:.2f}".format(fps.fps()))
print("[INFO] cleaning up...")
writer.release()
vs.release()