import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiClient {
  static const String _defaultBaseUrl = 'https://backend-nine-orpin-39.vercel.app';

  static String? _accessToken;
  static String? _refreshToken;

  static Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _accessToken = prefs.getString('access_token');
    _refreshToken = prefs.getString('refresh_token');
  }

  static String get baseUrl => _defaultBaseUrl;

  static String? get refreshToken => _refreshToken;

  static Map<String, String> get _headers {
    final headers = <String, String>{
      'Content-Type': 'application/json',
    };
    if (_accessToken != null) {
      headers['Authorization'] = 'Bearer $_accessToken';
    }
    return headers;
  }

  static Future<void> setTokens(
      String accessToken, String refreshToken) async {
    _accessToken = accessToken;
    _refreshToken = refreshToken;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('access_token', accessToken);
    await prefs.setString('refresh_token', refreshToken);
  }

  static Future<void> clearTokens() async {
    _accessToken = null;
    _refreshToken = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('access_token');
    await prefs.remove('refresh_token');
  }

  static Future<bool> hasToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.containsKey('access_token');
  }

  static Future<Map<String, dynamic>> get(String path,
      {Map<String, String>? queryParams}) async {
    final uri = Uri.parse('$baseUrl$path')
        .replace(queryParameters: queryParams);
    final response = await http.get(uri, headers: _headers);
    return _handleMapResponse(response);
  }

  static Future<List<dynamic>> getList(String path,
      {Map<String, String>? queryParams}) async {
    final uri = Uri.parse('$baseUrl$path')
        .replace(queryParameters: queryParams);
    final response = await http.get(uri, headers: _headers);
    return _handleListResponse(response);
  }

  static Future<Map<String, dynamic>> post(String path,
      {Map<String, dynamic>? body}) async {
    final uri = Uri.parse('$baseUrl$path');
    final response = await http.post(
      uri,
      headers: _headers,
      body: body != null ? jsonEncode(body) : null,
    );
    return _handleMapResponse(response);
  }

  static Future<Map<String, dynamic>> put(String path,
      {Map<String, dynamic>? body}) async {
    final uri = Uri.parse('$baseUrl$path');
    final response = await http.put(
      uri,
      headers: _headers,
      body: body != null ? jsonEncode(body) : null,
    );
    return _handleMapResponse(response);
  }

  static Future<Map<String, dynamic>> delete(String path) async {
    final uri = Uri.parse('$baseUrl$path');
    final response = await http.delete(uri, headers: _headers);
    return _handleMapResponse(response);
  }

  static Map<String, dynamic> _handleMapResponse(http.Response response) {
    final decoded = jsonDecode(response.body);
    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (decoded is List) {
        return {'data': decoded};
      }
      return decoded as Map<String, dynamic>;
    }
    if (decoded is Map<String, dynamic>) {
      throw ApiException(
        statusCode: response.statusCode,
        message: decoded['detail'] as String? ?? 'Something went wrong',
      );
    }
    throw ApiException(
      statusCode: response.statusCode,
      message: 'Something went wrong',
    );
  }

  static List<dynamic> _handleListResponse(http.Response response) {
    final decoded = jsonDecode(response.body);
    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (decoded is List) {
        return decoded;
      }
      throw ApiException(
        statusCode: response.statusCode,
        message: 'Expected list response',
      );
    }
    if (decoded is Map<String, dynamic>) {
      throw ApiException(
        statusCode: response.statusCode,
        message: decoded['detail'] as String? ?? 'Something went wrong',
      );
    }
    throw ApiException(
      statusCode: response.statusCode,
      message: 'Something went wrong',
    );
  }
}

class ApiException implements Exception {
  final int statusCode;
  final String message;

  ApiException({required this.statusCode, required this.message});

  @override
  String toString() => message;
}
