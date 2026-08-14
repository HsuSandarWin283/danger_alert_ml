"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { Capacitor } from "@capacitor/core"

const THRESHOLD = 80
const MAX_PULL = 120

export default function PullToRefresh({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const [pullDistance, setPullDistance] = useState(0)
  const [refreshing, setRefreshing] = useState(false)
  const [isPulling, setIsPulling] = useState(false)
  const startY = useRef(0)

  const doRefresh = () => {
    if (Capacitor.isNativePlatform()) {
      window.location.reload()
    } else {
      router.refresh()
    }
  }

  useEffect(() => {
    const onTouchStart = (e: TouchEvent) => {
      if (window.scrollY <= 0 && !refreshing) {
        startY.current = e.touches[0].clientY
        setIsPulling(true)
      }
    }

    const onTouchMove = (e: TouchEvent) => {
      if (!isPulling || refreshing) return
      const diff = e.touches[0].clientY - startY.current
      if (diff > 0) {
        setPullDistance(Math.min(diff, MAX_PULL))
        e.preventDefault()
      }
    }

    const onTouchEnd = () => {
      if (!isPulling) return
      setIsPulling(false)

      if (pullDistance >= THRESHOLD && !refreshing) {
        setRefreshing(true)
        setPullDistance(0)
        doRefresh()
        setRefreshing(false)
      } else {
        setPullDistance(0)
      }
    }

    const onMouseDown = (e: MouseEvent) => {
      if (window.scrollY <= 0 && !refreshing) {
        startY.current = e.clientY
        setIsPulling(true)
      }
    }

    const onMouseMove = (e: MouseEvent) => {
      if (!isPulling || refreshing) return
      const diff = e.clientY - startY.current
      if (diff > 0) {
        setPullDistance(Math.min(diff, MAX_PULL))
      }
    }

    const onMouseUp = () => {
      if (!isPulling) return
      setIsPulling(false)

      if (pullDistance >= THRESHOLD && !refreshing) {
        setRefreshing(true)
        setPullDistance(0)
        doRefresh()
        setRefreshing(false)
      } else {
        setPullDistance(0)
      }
    }

    document.addEventListener("touchstart", onTouchStart, { passive: true })
    document.addEventListener("touchmove", onTouchMove, { passive: false })
    document.addEventListener("touchend", onTouchEnd)
    document.addEventListener("mousedown", onMouseDown)
    document.addEventListener("mousemove", onMouseMove)
    document.addEventListener("mouseup", onMouseUp)

    return () => {
      document.removeEventListener("touchstart", onTouchStart)
      document.removeEventListener("touchmove", onTouchMove)
      document.removeEventListener("touchend", onTouchEnd)
      document.removeEventListener("mousedown", onMouseDown)
      document.removeEventListener("mousemove", onMouseMove)
      document.removeEventListener("mouseup", onMouseUp)
    }
  }, [pullDistance, refreshing, isPulling])

  const progress = Math.min(pullDistance / THRESHOLD, 1)
  const rotation = progress * 360

  return (
    <div className="relative min-h-screen">
      <div
        className="fixed top-0 left-0 right-0 z-50 flex justify-center overflow-hidden transition-all"
        style={{ height: refreshing ? 50 : pullDistance }}
      >
        <div
          className="flex items-center justify-center"
          style={{
            opacity: progress,
            transform: `rotate(${refreshing ? 360 : rotation}deg)`,
            transition: refreshing ? "transform 0.5s linear" : "none",
          }}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M21 12a9 9 0 11-6.219-8.56" />
            <polyline points="21 3 21 12 12 12" />
          </svg>
        </div>
      </div>

      <div
        style={{
          transform: `translateY(${refreshing ? 50 : pullDistance}px)`,
          transition: isPulling ? "none" : "transform 0.3s ease",
        }}
      >
        {children}
      </div>
    </div>
  )
}
