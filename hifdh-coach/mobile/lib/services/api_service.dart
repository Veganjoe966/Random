import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// API client for Hifdh Coach backend.
/// Handles JWT auth, token refresh, and all API calls.
class ApiService {
  static const String _baseUrl = 'http://localhost:8000/api/v1';

  final Dio _dio;
  final FlutterSecureStorage _storage;

  ApiService()
      : _dio = Dio(BaseOptions(
          baseUrl: _baseUrl,
          connectTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 30),
        )),
        _storage = const FlutterSecureStorage() {
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await _storage.read(key: 'access_token');
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
      onError: (error, handler) async {
        if (error.response?.statusCode == 401) {
          final refreshed = await _refreshToken();
          if (refreshed) {
            // Retry the failed request
            final token = await _storage.read(key: 'access_token');
            error.requestOptions.headers['Authorization'] = 'Bearer $token';
            final response = await _dio.fetch(error.requestOptions);
            handler.resolve(response);
            return;
          }
        }
        handler.next(error);
      },
    ));
  }

  // ── Auth ───────────────────────────────────────────────────────────
  Future<Map<String, dynamic>> login(String email, String password) async {
    final response = await _dio.post('/auth/login', data: {
      'email': email,
      'password': password,
    });
    await _storeTokens(response.data);
    return response.data;
  }

  Future<bool> _refreshToken() async {
    final refreshToken = await _storage.read(key: 'refresh_token');
    if (refreshToken == null) return false;
    try {
      final response = await _dio.post('/auth/refresh', data: {
        'refresh_token': refreshToken,
      });
      await _storeTokens(response.data);
      return true;
    } catch (_) {
      await logout();
      return false;
    }
  }

  Future<void> _storeTokens(Map<String, dynamic> data) async {
    await _storage.write(key: 'access_token', value: data['access_token']);
    await _storage.write(key: 'refresh_token', value: data['refresh_token']);
  }

  Future<void> logout() async {
    await _storage.deleteAll();
  }

  // ── Recitations ───────────────────────────────────────────────────
  Future<Map<String, dynamic>> uploadRecitation({
    required File audioFile,
    required int surahNumber,
    required int ayahStart,
    required int ayahEnd,
    String recitationType = 'new_lesson',
  }) async {
    final formData = FormData.fromMap({
      'surah_number': surahNumber,
      'ayah_start': ayahStart,
      'ayah_end': ayahEnd,
      'recitation_type': recitationType,
      'audio': await MultipartFile.fromFile(audioFile.path),
    });
    final response = await _dio.post('/recitations/upload', data: formData);
    return response.data;
  }

  Future<Map<String, dynamic>> getRecitation(String id) async {
    final response = await _dio.get('/recitations/$id');
    return response.data;
  }

  // ── Schedule ──────────────────────────────────────────────────────
  Future<Map<String, dynamic>> getMySchedule() async {
    final response = await _dio.get('/students/me/schedule');
    return response.data;
  }

  // ── Profile ───────────────────────────────────────────────────────
  Future<Map<String, dynamic>> getMyProfile() async {
    final response = await _dio.get('/students/me/profile');
    return response.data;
  }
}
