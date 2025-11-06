// Modified 2025-10-14 by A. Wellisz to be more versatile (instead of tied to a specific project)

//=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
//
// Copyright (c) 2002 JY Horiba, Inc
// All Rights Reserved
//
// THIS IS UNPUBLISHED PROPRIETARY SOURCE CODE OF JY Horiba, Inc
// The copyright notice above does not evidence any
// actual or intended publication of such source code.
//
// *--------------------------------------------------*
//
//	Module Name:		JYDeviceSink
//
//	Original Author:J. McKitrick/J. Martin
//
//	Abstract:		This module serves to connect the applciation to a JYDevice (CCD, Mono, etc...)
//							It requires that you create an MFC project with ActiveX and Automation enabled.
//							IMPORTANT: ATL Must be supported in the project.  To do this, after you've created
//							the project, from the class view, right-click and select insert New ATL object.  Select
//							'OK' to the prompt about supporting ATL.  Then you just need to cancel out of the resulting 
//							dialog box (Object Selection).  This adds ATL support to your MFC project.
//              The class below must also be modified to support the appropriate "Parent" of this sink.  This parent can 
//              be a CWnd object or any type of object.  It must simply support the functions you choose to 
//              "call back" in the event handler functions.  Or you could simply do all of your event handling in the
//							jyDeviceSink class (not recommended, but possible). 
//
//	Dependencies:
//
//	Creation Date:  2/26/03
//
//	Implementational Notes:
//
//________+++++________
// JYDeviceSink.cpp: implementation of the CJYDeviceSink class.
//
//////////////////////////////////////////////////////////////////////



#include "stdafx.h"
#include "resource.h"

#include "JYDeviceSink.h"


#ifdef _DEBUG
#undef THIS_FILE
static char THIS_FILE[]=__FILE__;
#define new DEBUG_NEW
#endif

//////////////////////////////////////////////////////////////////////
// Construction/Destruction
//////////////////////////////////////////////////////////////////////

// CJYDeviceSink::CJYDeviceSink( CMonoCCD_Cpp_2010Dlg *parentPtr, IJYSystemReqd *eventSource )
CJYDeviceSink::CJYDeviceSink(IJYDeviceEvents* parentPtr, IJYSystemReqd* eventSource)
	: m_eventSourcePtr(eventSource), m_parentPtr(parentPtr)
{
	// Keep a reference to the parent we will "call back" when the event occurs
	// m_parentPtr = parentPtr;
	// Keep a reference to the source object of the event and addref for proper lifetime maintenance
	// m_eventSourcePtr = eventSource;
	if (m_eventSourcePtr) m_eventSourcePtr->AddRef();
	// Establish the (ATL) connection to the source...
	HRESULT hr = DispEventAdvise( m_eventSourcePtr );
	_ASSERT( SUCCEEDED(hr));
}

CJYDeviceSink::~CJYDeviceSink()
{
	if (m_eventSourcePtr) {
		// Release our connection to the sink....
		DispEventUnadvise(m_eventSourcePtr);
		// Release our reference to the source
		m_eventSourcePtr->Release();
		m_eventSourcePtr = nullptr;
	}
}



//=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=
//	ORIG AUTHOR:	J. Martin
//
//	PARAMETERS:		[in] - status - indicator that can be used to convey status information.  This
//												information is available in the event, but the status parameter can 
//												be used to avoid unnecessary access to the eventInfo object
//								[in] - eventInfo - Interface used to encapsulate the details of the event that 
//												has occurred.  The event will contain a reference to the source of the event
//												and more detailed information regarding any error conditions that occurred.
//
//	DESCRIPTION:	Handler for the connected device when it fires initialized events
//
//	RETURNS:
//
//	NOTES:
//_______________
void CJYDeviceSink::OnInitialized( long status, IJYEventInfo *eventInfo )
{
	if (m_parentPtr) m_parentPtr->ReceivedDeviceInitialized( status, eventInfo );
}
//=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=
//	ORIG AUTHOR:	J. Martin
//
//	PARAMETERS:		[in] - status - indicator that can be used to convey status information.  This
//												information is available in the event, but the status parameter can 
//												be used to avoid unnecessary access to the eventInfo object
//								[in] - eventInfo - Interface used to encapsulate the details of the event that 
//												has occurred.  The event will contain a reference to the source of the event
//												and more detailed information regarding any error conditions that occurred.
//
//	DESCRIPTION:	Handler for the connected device when it fires status events
//
//	RETURNS:
//
//	NOTES:
//_______________
void CJYDeviceSink::OnOperationStatus( long status, IJYEventInfo *eventInfo )
{
	if (m_parentPtr) m_parentPtr->ReceivedDeviceStatus( status, eventInfo );
}

//=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=
//	ORIG AUTHOR:	J. Martin
//
//	PARAMETERS:		[in] - updateType - indicator that can be used to convey the type of update.  This
//												information is available in the event, but the status parameter can 
//												be used to avoid unnecessary access to the eventInfo object
//								[in] - eventInfo - Interface used to encapsulate the details of the event that 
//												has occurred.  The event will contain a reference to the source of the event
//												and more detailed information regarding any error conditions that occurred.
//
//	DESCRIPTION:  Handler for the connected device when it fires update events.  
//
//	RETURNS:
//
//	NOTES:				Currently updates are only used for data and the type JY_DATA_UPDATE = 100
//_______________
#define JY_UPDATE_TYPE_DATA 100
void CJYDeviceSink::OnUpdate( long updateType, IJYEventInfo *eventInfo )
{
	if ( updateType == JY_UPDATE_TYPE_DATA )
		{
		AtlTrace("Data Update Received[%ld]\n", updateType);
		}
	else
		{
		AtlTrace("NON-Data Update Received[%ld]\n", updateType);
		}
	if (m_parentPtr) m_parentPtr->ReceivedDeviceUpdate( updateType, eventInfo );
}

//=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=_=
//	ORIG AUTHOR:	J. Martin
//
//	PARAMETERS:		[in] - status - indicator that can be used to convey status information.  This
//												information is available in the event, but the status parameter can 
//												be used to avoid unnecessary access to the eventInfo object
//								[in] - eventInfo - Interface used to encapsulate the details of the event that 
//												has occurred.  The event will contain a reference to the source of the event
//												and more detailed information regarding any error conditions that occurred.
//
//	DESCRIPTION:	Handler for when device encounters a critical error  
//
//	RETURNS:
//
//	NOTES:
//_______________
void CJYDeviceSink::OnCriticalError( long status, IJYEventInfo *eventInfo )
{
	if (m_parentPtr) m_parentPtr->ReceivedDeviceCriticalError( status, eventInfo );
}