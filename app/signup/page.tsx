import Link from 'next/link'
import SignupForm from '@/app/ui/signup-form'

export const metadata = {
  title: 'Sign Up',
  description: 'Sign up for AI Personal Safety Companion',
}

export default function SignupPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h1 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            Sign Up
          </h1>
          <p className="mt-2 text-center text-sm text-gray-600">
            Create an account to get started.
          </p>
        </div>
        <div className="mt-8 bg-white py-8 px-6 shadow-lg rounded-lg">
          <SignupForm />
        </div>
        <p className="text-center text-sm text-gray-600">
          Already have an account?{' '}
          <Link href="/login" className="font-medium text-blue-600 hover:text-blue-500">
            Log In
          </Link>
        </p>
      </div>
    </div>
  )
}
