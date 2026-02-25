import 'package:flutter/material.dart';

/// Daily revision schedule screen.
/// Shows AI-generated review queue sorted by retention urgency.
class ScheduleScreen extends StatelessWidget {
  const ScheduleScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text("Today's Revision",
                style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                    )),
            const SizedBox(height: 4),
            Text(
              'Prioritized by memory retention predictions',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
            const SizedBox(height: 16),

            // Summary bar
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    _SummaryChip(label: 'Total', value: '—', color: Colors.grey),
                    _SummaryChip(
                        label: 'Critical', value: '—', color: Colors.red),
                    _SummaryChip(
                        label: 'High', value: '—', color: Colors.orange),
                    _SummaryChip(
                        label: 'Est. Time', value: '—', color: Colors.blue),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Schedule items
            Expanded(
              child: Center(
                child: Text(
                  'Schedule items will appear here once connected to the API.',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                  textAlign: TextAlign.center,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SummaryChip extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _SummaryChip({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(value,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: color,
                )),
        Text(label, style: Theme.of(context).textTheme.bodySmall),
      ],
    );
  }
}
