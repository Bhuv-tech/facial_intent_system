import React from 'react'
import TeacherDashboard from './TeacherDashboard'
import StudentDashboard from './StudentDashboard'
import DoctorDashboard from './DoctorDashboard'
import PatientInterface from './PatientInterface'
import HRDashboard from './HRDashboard'
import CandidateInterface from './CandidateInterface'

export default function Dashboard({ user, onLogout }) {
  const isStudent = user.user_type === 'student'

  if (user.context === 'doctor') {
    return isStudent 
      ? <PatientInterface user={user} onLogout={onLogout} /> 
      : <DoctorDashboard user={user} onLogout={onLogout} />
  }

  if (user.context === 'hr') {
    return isStudent
      ? <CandidateInterface user={user} onLogout={onLogout} />
      : <HRDashboard user={user} onLogout={onLogout} />
  }

  return isStudent 
    ? <StudentDashboard user={user} onLogout={onLogout} /> 
    : <TeacherDashboard user={user} onLogout={onLogout} />
}
