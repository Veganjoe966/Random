import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'screens/home_screen.dart';
import 'screens/record_screen.dart';
import 'screens/schedule_screen.dart';
import 'screens/progress_screen.dart';
import 'screens/login_screen.dart';

void main() {
  runApp(const ProviderScope(child: HifdhCoachApp()));
}

final _router = GoRouter(
  initialLocation: '/login',
  routes: [
    GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
    ShellRoute(
      builder: (context, state, child) => AppShell(child: child),
      routes: [
        GoRoute(path: '/', builder: (_, __) => const HomeScreen()),
        GoRoute(path: '/record', builder: (_, __) => const RecordScreen()),
        GoRoute(path: '/schedule', builder: (_, __) => const ScheduleScreen()),
        GoRoute(path: '/progress', builder: (_, __) => const ProgressScreen()),
      ],
    ),
  ],
);

class HifdhCoachApp extends StatelessWidget {
  const HifdhCoachApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'Hifdh Coach',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF2E7D4F), // Islamic green
          brightness: Brightness.light,
        ),
        useMaterial3: true,
      ),
      darkTheme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF2E7D4F),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      routerConfig: _router,
    );
  }
}

class AppShell extends StatelessWidget {
  final Widget child;
  const AppShell({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: child,
      bottomNavigationBar: NavigationBar(
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home), label: 'Home'),
          NavigationDestination(icon: Icon(Icons.mic), label: 'Record'),
          NavigationDestination(icon: Icon(Icons.calendar_today), label: 'Schedule'),
          NavigationDestination(icon: Icon(Icons.trending_up), label: 'Progress'),
        ],
        selectedIndex: _calculateIndex(GoRouterState.of(context).uri.toString()),
        onDestinationSelected: (index) {
          final routes = ['/', '/record', '/schedule', '/progress'];
          context.go(routes[index]);
        },
      ),
    );
  }

  int _calculateIndex(String location) {
    if (location.startsWith('/record')) return 1;
    if (location.startsWith('/schedule')) return 2;
    if (location.startsWith('/progress')) return 3;
    return 0;
  }
}
