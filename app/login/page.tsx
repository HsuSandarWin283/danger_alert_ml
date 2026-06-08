import LoginForm from '@/app/ui/login-form'

export const metadata = {
  title: 'Log In',
  description: 'Log in to AI Personal Safety Companion',
}

export default function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h1 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            Log In
          </h1>
          <p className="mt-2 text-center text-sm text-gray-600">
            Log in to your account to access your safety dashboard.
          </p>
        </div>
        <div className="mt-8 bg-white py-8 px-6 shadow-lg rounded-lg">
          <LoginForm />
        </div>
        <p className="text-center text-sm text-gray-600">
          Don&rsquo;t have an account?{' '}
          <a href="/signup" className="font-medium text-blue-600 hover:text-blue-500">
            Sign Up
          </a>
        </p>
      </div>
    </div>
  )
}
