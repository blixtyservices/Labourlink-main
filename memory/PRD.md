# LabourLink AI - Product Requirements

## Vision
India's most premium labour hiring marketplace. Customers instantly hire verified nearby workers; workers receive nearby job requests instantly. Inspired by Uber, Urban Company, Stripe.

## Tagline
**RIGHT WORKER. RIGHT NOW.**

## Brand
- Primary: Premium Construction Gold #F6B100
- Secondary: Black #0F1115
- Accent: White
- Typography: Bold, rounded, modern, premium
- Glassmorphism cards, soft shadows, 24px+ radius

## Implemented Features (v1 - MVP+)
### Customer
- Premium landing page (gold/black hero)
- Email/password auth (JWT, 30-day tokens)
- Home dashboard: search, categories, AI-powered recommendations, top-rated workers
- Browse / category screen with sort & filter
- Worker profile: cover, avatar, metrics, skills, reviews, call/WhatsApp/chat actions
- Booking flow: date/time/duration/address/payment method, total summary
- Booking confirmation screen
- Bookings list with status badges + actions
- Favorites
- Chat (polled real-time) - opens from booking & profile
- Star ratings & reviews

### Worker
- Worker signup & onboarding (category, skills, experience, wages, city, bio)
- Worker Dashboard: online/offline toggle, earnings (today/week/month/lifetime/pending/balance/withdrawn), stats grid
- Withdraw flow (UPI/bank) with status tracking
- Booking requests (accept/reject/start/complete)

### AI
- Emergent LLM key + Claude Sonnet 4.6 for ranked worker recommendations on Home

### Live status
- Worker "online" status visible on cards (green dot + LIVE pill)
- Status toggle in worker dashboard

## Tech
- Backend: FastAPI, MongoDB (Motor), JWT auth (PyJWT + bcrypt)
- Frontend: Expo Router (React Native), Reanimated, expo-image, gorhom/bottom-sheet, AsyncStorage
- AI: emergentintegrations + Claude Sonnet 4.6

## Deferred to v2
- Razorpay payments integration
- Google OAuth & mobile OTP login
- Google Maps live GPS tracking
- FCM push notifications
- Admin web dashboard
- Multi-language (Hindi/English)
- Voice notes & file attachments in chat
- Document verification (Aadhaar/PAN upload)
