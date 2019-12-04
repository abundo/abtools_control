#!/usr/bin/env python3
import api

if __name__ == '__main__':
	print("Starting development server")
	api.app.run(host='0.0.0.0', debug=True, threaded=False, processes=1)
