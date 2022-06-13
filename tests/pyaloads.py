oper_state = {
	'id': 99,
	'status': 0,
	'desc': None,
	'data': {
		'timeDelta': 15,
		'commandJson': {
			'OPER': '{"OPER":{"TURN_ON_OFF":"OFF","AC_MODE":"COOL","SPT":"24","FANSPD":"AUTO","VSWING":"OFF","SLEEP":"OFF","HSWING":"OFF","CLEAR_FILT":"OFF","IDU_PN":"","IFEEL":"OFF","MSGTYPE":"OPER","OP_VAL_ERR":"OK","SHABAT":"OFF","TIMER":"OFF","TURBO":"OFF"}}',
			'DIAG_L2': '{"DIAG_L2":{"I_RAT":"24","O_ODU_MODE":"COOL","IDU_FAN":"AUTO","IDU_PN":"","MSGTYPE":"DIAG_L2","O_OAT":""}}'
		},
		'res': 0,
		'res_desc': None
	}
}

resp = {
	'id': 99,
	'status': 0,
	'desc': None,
	'data': {
		'devices': [
            {
			'providerName': None,
			'deviceTypeName': 'A/C',
			'manufactor': 'Midea',
			'photoId': None,
			'permissions': 15,
			'deviceTypeId': 1,
			'name': 'סלון',
			'status': 1,
			'providerid': 1,
			'latitude': None,
			'longitude': None,
			'location': None,
			'sn': 'XXXXXX',
			'mac': 'XXXXX',
			'model': 'XXXXX',
			'hwVersion': None,
			'fmVersion': None,
			'userId': 99999,
			'manufactorId': 2,
			'iconId': '1',
			'hasImage': False,
			'deviceToken': 'XXXXX',
			'mqttId': 'XXXXX',
			'enableEvents': True,
			'isActivated': False,
			'logLevel': None,
			'lastIntervalActivity': None,
			'PowerOnID': None,
			'IsDebugMode': False,
			'regdate': '2021-03-31T21:12:39',
			'id': 9999
		    }
        ],
		'res': 0,
		'res_desc': None
	}
}