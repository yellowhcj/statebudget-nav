#include <vector>
#include <queue>
#include <tuple>
#include <cmath>
#include <functional>
#ifdef _WIN32
#define API extern "C" __declspec(dllexport)
#else
#define API extern "C"
#endif
API int next4(const unsigned char* a,int w,int h,int start,int goal,int* expanded){
 using Node=std::tuple<int,int,int>;std::priority_queue<Node,std::vector<Node>,std::greater<Node>> heap;
 auto H=[&](int p){return std::abs(p%w-goal%w)+std::abs(p/w-goal/w);};
 std::vector<int> dist(w*h,1000000000),parent(w*h,-1);dist[start]=0;heap.emplace(H(start),0,start);*expanded=0;
 const int dx[4]={1,0,-1,0},dy[4]={0,1,0,-1};
 while(!heap.empty()){
  auto[f,g,p]=heap.top();heap.pop();if(g!=dist[p])continue;++*expanded;if(p==goal)break;
  for(int d=0;d<4;++d){int x=p%w+dx[d],y=p/w+dy[d];if(x<0||x>=w||y<0||y>=h)continue;int q=y*w+x;if(a[q]==2)continue;
   int ng=g+(a[q]==1?1:2);if(ng<dist[q]){dist[q]=ng;parent[q]=p;heap.emplace(ng+H(q),ng,q);}}
 }
 if(parent[goal]<0)return start;int p=goal;while(parent[p]!=start)p=parent[p];return p;
}
API double oracle8(const unsigned char* a,int w,int h,int start,int goal){
 using Node=std::tuple<double,double,int>;std::priority_queue<Node,std::vector<Node>,std::greater<Node>> heap;
 auto H=[&](int p){int dx=std::abs(p%w-goal%w),dy=std::abs(p/w-goal/w);return std::max(dx,dy)+(std::sqrt(2.)-1)*std::min(dx,dy);};
 std::vector<double>dist(w*h,1e100);dist[start]=0;heap.emplace(H(start),0,start);
 while(!heap.empty()){
  auto[f,g,p]=heap.top();heap.pop();if(g!=dist[p])continue;if(p==goal)return g;
  for(int dx=-1;dx<=1;++dx)for(int dy=-1;dy<=1;++dy){if(!dx&&!dy)continue;int x=p%w+dx,y=p/w+dy;if(x<0||x>=w||y<0||y>=h)continue;
   int q=y*w+x;if(a[q]!=1)continue;if(dx&&dy&&(a[(p/w)*w+x]!=1||a[y*w+p%w]!=1))continue;
   double ng=g+(dx&&dy?std::sqrt(2.):1.);if(ng<dist[q]){dist[q]=ng;heap.emplace(ng+H(q),ng,q);}}
 }return -1;
}
