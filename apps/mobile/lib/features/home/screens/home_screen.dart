import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/widgets/product_grid_section.dart';
import '../../../providers/auth_provider.dart';
import '../../../providers/cart_provider.dart';
import '../../../providers/category_provider.dart';
import '../../../providers/product_provider.dart';
import '../widgets/top_bar.dart';
import '../widgets/gender_filter_tabs.dart';
import '../widgets/category_chips.dart';
import '../widgets/hero_banner.dart';
import '../widgets/brand_strip.dart';
import '../widgets/promo_grid.dart';
import '../widgets/banner_section.dart';
import '../../cart/screens/cart_screen.dart';
import '../../search/screens/search_screen.dart';
import '../../product/screens/product_list_screen.dart';
import '../../wishlist/screens/wishlist_screen.dart';
import '../../profile/screens/address_list_screen.dart';
import '../../profile/screens/profile_screen.dart';

const _sponsoredImages = [
  'https://ucarecdn.com/ec917a93-25f1-49d4-8f87-8d66b5408d78/image.png',
  'https://ucarecdn.com/4452e72b-d2c5-48ec-a4d8-6263ef5c6ae9/image.png',
  'https://ucarecdn.com/ae220190-9638-4e13-994a-7bc8e9c7fe46/image.png',
  'https://ucarecdn.com/cd49167d-f39f-4cdf-aa35-7a960a635b1a/image.png',
  'https://ucarecdn.com/023b6918-ff20-4145-89e0-fb81974f339c/image.png',
];

const _topCategoryImages = [
  'https://ucarecdn.com/a6b161dc-6fea-4159-89d1-795014ab7978/image.png',
  'https://ucarecdn.com/a5a87d1c-de3e-4a1e-9185-779b6665c542/image.png',
  'https://ucarecdn.com/e19a8c42-e0c8-4f89-ab59-c8cda3aa0302/image.png',
  'https://ucarecdn.com/7d1ee812-db00-453c-9f74-7748aecd5bf5/image.png',
];

const _brandsInFocusImages = [
  'https://ucarecdn.com/b6795858-3b22-4d06-bf0e-16f1e22452e4/image.png',
  'https://ucarecdn.com/d6f5f6e2-958a-415c-a56a-4427ae489dcb/image.png',
  'https://ucarecdn.com/be852418-5a5d-47fb-a0a2-7f4492317765/image.png',
  'https://ucarecdn.com/ee4b2912-9446-48aa-b508-d4ba487c9114/image.png',
];

const _brandToExploreImages = [
  'https://ucarecdn.com/c04f320a-d724-4b65-bf69-b3c996e60c50/image.png',
  'https://ucarecdn.com/c04f320a-d724-4b65-bf69-b3c996e60c50/image.png',
  'https://ucarecdn.com/43af3c58-b1e1-4995-82e0-e916329aee81/image.png',
  'https://ucarecdn.com/6bf37590-07cb-4d30-a977-3fc3329b1546/image.png',
];

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<CategoryProvider>().fetchCategories();
      context.read<ProductProvider>().fetchProducts();
    });
  }

  @override
  Widget build(BuildContext context) {
    final cartCount = context.watch<CartProvider>().count;
    final categoryProvider = context.watch<CategoryProvider>();
    final categories = categoryProvider.filteredCategories;
    final productProvider = context.watch<ProductProvider>();
    final featuredProducts = productProvider.featuredProducts;
    final allProducts = productProvider.products;
    return Scaffold(
      backgroundColor: AppColors.surface,
      body: SafeArea(
        child: Column(
          children: [
            TopBar(
              cartCount: cartCount,
              onSearchTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const SearchScreen()),
              ),
              onWishlistTap: () {
                final auth = context.read<AuthProvider>();
                if (!auth.isLoggedIn) {
                  Navigator.pushNamed(context, '/login');
                } else {
                  Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => const WishlistScreen()),
                  );
                }
              },
              onCartTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const CartScreen()),
              ),
              onNotificationTap: () {},
              onProfileTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const ProfileScreen()),
              ),
              onAddressTap: () => Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => const AddressListScreen(),
                ),
              ),
            ),
            Expanded(
              child: SingleChildScrollView(
                child: Column(
                  children: [
                    GenderFilterTabs(
                      selectedGender: categoryProvider.selectedGender,
                      onTabChanged: (tab) =>
                          context.read<CategoryProvider>().setGender(tab),
                    ),
                    CategoryChips(
                      categories: categories,
                      onCategoryTap: (cat) => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => ProductListScreen(category: cat),
                        ),
                      ),
                    ),
                    const HeroBanner(),
                    const BrandStrip(),
                    const PromoGrid(
                      onBrandDayTap: null,
                      onStylishStealsTap: null,
                    ),
                    const BannerSection(
                      title: 'SPONSORED PRODUCTS',
                      imageUrls: _sponsoredImages,
                    ),
                    const BannerSection(
                      title: 'TOP CATEGORIES',
                      imageUrls: _topCategoryImages,
                    ),
                    const BannerSection(
                      title: 'BRANDS IN FOCUS',
                      imageUrls: _brandsInFocusImages,
                    ),
                    const BannerSection(
                      title: 'BRAND TO EXPLORE',
                      imageUrls: _brandToExploreImages,
                    ),
                    ProductGridSection(
                      title: 'Featured Products',
                      subtitle: 'Handpicked just for you',
                      products: featuredProducts,
                      onViewAll: () => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => ProductListScreen(title: 'Featured'),
                        ),
                      ),
                    ),
                    if (allProducts.isNotEmpty)
                      ProductGridSection(
                        title: 'ALL PRODUCTS',
                        products: allProducts,
                      ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
